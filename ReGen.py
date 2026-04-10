from dotenv import load_dotenv
load_dotenv()

import argparse
import os
import subprocess
import sys
from input_processing import Reader, chunker
from models import Model
from extractor import Extractor
from analyzer import Analyzer
from reportgenerator import reportMaker

# config.py (or in Main.py)
def get_mode_config(mode, num_sources):
    base = {
        "brief": {
            "insights_per_source": 2,
            "max_themes": 3,
            "max_takeaways": 3,
            "section_depth": "1-2 sentences per point",
            "exec_summary": "1 short paragraph",
            "include_per_source_sections": False,
            "include_cross_source": False,
            "include_clusters": False,
            "cluster_threshold": None,
        },
        "standard": {
            "insights_per_source": 5,
            "max_themes": 3 + num_sources,
            "max_takeaways": 3 + num_sources,
            "section_depth": "1 paragraph per point",
            "exec_summary": "2-3 paragraphs",
            "include_per_source_sections": False,
            "include_cross_source": True,
            "include_clusters": num_sources >= 3,
            "cluster_threshold": "high",           # only the strongest connections
            "sectioned_generation": True,
        },
        "detailed": {
            "insights_per_source": 10,
            "max_themes": 4 + (num_sources * 2),
            "max_takeaways": 5 + num_sources,
            "section_depth": "2-3 paragraphs per point with examples, context, and implications",
            "exec_summary": "3-4 paragraphs",
            "include_per_source_sections": True,
            "include_cross_source": True,
            "include_clusters": num_sources >= 2,
            "cluster_threshold": "medium",         # high + medium relevance clusters
            "sectioned_generation": True,
        },
    }
    return base[mode]


def parse_args():
    parser = argparse.ArgumentParser(
        prog="regen",
        description="ReGen: AI-powered report generator"
    )
    # allow multiple sources as command-line arguments, or a .txt file with one source per line
    parser.add_argument(
        "sources", nargs="+",
        help="URLs, file paths, or .txt files containing one source per line"
    )
    #pick amount of detal that you want in the report, more detail = more tokens used = higher cost
    parser.add_argument(
        "-m", "--mode", choices=["brief", "standard", "detailed"],
        default="standard", help="Report detail level (default: standard)"
    )
    #output format, default to html
    parser.add_argument(
        "-o", "--output", choices=["html", "pdf", "docx"],
        default="html", help="Output format (default: html)"
    )
    #name of the output file without extension
    parser.add_argument(
        "--name", default="report",
        help="Output filename without extension (default: report)"
    )
    #LLM model to use, default to gpt-3.5-turbo, but allow any model supported by litell
    parser.add_argument(
        "--model", default="gpt-3.5-turbo",
        help="LLM model name (default: gpt-3.5-turbo)"
    )
    #option to auto render or not
    parser.add_argument(
        "--render", action="store_true", default=False,
        help="Auto-render the .qmd with Quarto after generation"
    )
    #verbose mode to show detailed progress, including chunk-level extraction and reduce steps
    parser.add_argument(
        "-v", "--verbose", action="store_true", default=False,
        help="Show detailed progress (chunk-level extraction, reduce steps)"
    )
    #quiet mode to suppress all output except errors and final report path
    parser.add_argument(
        "-q", "--quiet", action="store_true", default=False,
        help="Suppress all output except errors and final report path"
    )
    return parser.parse_args()


def resolve_sources(raw_sources):
    """Expand .txt files into individual sources, one per line."""
    sources = []
    for s in raw_sources:
        if s.endswith(".txt") and os.path.isfile(s):
            with open(s, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        sources.append(line)
        else:
            sources.append(s)
    return sources

# Simple logging function that respects quiet mode
def log(msg, quiet=False):
    if not quiet:
        print(msg)


def main():
    args = parse_args()

    if args.verbose and args.quiet:
        print("Error: --verbose and --quiet cannot be used together.", file=sys.stderr)
        sys.exit(1)

    sources = resolve_sources(args.sources)
    #error handling for no sources
    if not sources:
        print("Error: No sources provided.", file=sys.stderr)
        sys.exit(1)

    mode = args.mode
    log(f"Running in {mode} mode with {len(sources)} sources...", args.quiet)
    # get model and config based on mode and number of sources
    model = Model(model_name=args.model)
    config = get_mode_config(mode, len(sources))

    # For each source, read, parse, chunk, and extract
    extractions = []
    log("Extracting information from sources...", args.quiet)
    for i, source in enumerate(sources, 1):
        log(f"\n[{i}/{len(sources)}] Processing: {source[:80]}...", args.quiet)
        try:
            #read the source and get the file type, send to relevent parser
            reader = Reader(source)
            #parse the data
            parsed = reader.parse()
            #chunk the data into smaller pieces for extraction
            chunks = chunker(parsed)
        #error handling
        except Exception as e:
            log(f"  Failed to read source: {e}", args.quiet)
            continue
        if not chunks:
            log(f"  No content extracted, skipping", args.quiet)
            continue
        log(f"  → {len(chunks)} chunks to extract", args.quiet)
        #extract key information from the chunks using the model, recursively make smaller and smaller until below max token size, then reduce all the chunks into one final extraction for this source
        extractor = Extractor(model=model, verbose=args.verbose)
        result = extractor.run(chunks)
        # Skip empty/unknown extractions
        if not result or (not result.get("entities") and not result.get("statistics") and not result.get("claims")):
            log(f"  No meaningful data extracted, skipping", args.quiet)
            continue
        extractions.append(result)
        log(f"  ✓ Source {i} done", args.quiet)

    if not extractions:
        print("No usable data from any source. Exiting.", file=sys.stderr)
        sys.exit(1)

    # Sanaylze each source's extraction, break into clusters if needed, if standard/detailed mode synthesize 
    # insights from medium/high relevance clusters, and identify key themes and takeaways across source
    #  then synthesize into overall insights and themes across sources
    log("Analyzing and synthesizing extracted information...", args.quiet)
    analyzer = Analyzer(model=model, config=config)
    analysis = analyzer.run(extractions)

    # use the analysis to generate a report in the requested format, save to disk, and optionally render with Quarto
    log("Generating report...", args.quiet)
    report = reportMaker(model=model, config=config)
    report_path = report.generate(analysis, report_name=args.name, output_format=args.output)
    log(f"Report saved to: {report_path}", args.quiet)

    # Step 6: Render with Quarto if requested
    if args.render:
        log("Rendering with Quarto...", args.quiet)
        result = subprocess.run(
            ["quarto", "render", report_path],
            capture_output=args.quiet,
        )
        if result.returncode == 0:
            rendered = report_path.replace(".qmd", f".{args.output}")
            print(rendered)
        else:
            print(f"Quarto render failed (exit code {result.returncode})", file=sys.stderr)
            if args.quiet and result.stderr:
                print(result.stderr.decode(), file=sys.stderr)
            sys.exit(1)
    elif not args.quiet:
        print(f"\nRun 'quarto render {report_path}' to render the report.")

if __name__ == "__main__":
    main()