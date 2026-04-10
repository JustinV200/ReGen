from dotenv import load_dotenv
load_dotenv()

from input_processing import Reader, chunker
from extractor import Model, Extractor
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
        },
    }
    return base[mode]







def main():
    sources = [
        "https://www.usatoday.com/story/news/health/2025/09/15/covid-19-september-2025-cases-variants-symptoms-vaccines/86163707007/",
        "https://www.cdc.gov/covid/php/surveillance/index.html",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC9874793/",
        "https://data.who.int/dashboards/covid19/summary",
        "https://www.cdc.gov/covid/about/index.html"

    ]
    mode = "detailed"
    print(f"Running in {mode} mode with {len(sources)} sources...")
    model = Model()
    config = get_mode_config(mode, len(sources))

    # Step 1-3: For each source, read, parse, chunk, and extract
    extractions = []
    print("Extracting information from sources...")
    for i, source in enumerate(sources, 1):
        print(f"\n[{i}/{len(sources)}] Processing: {source[:80]}...")
        reader = Reader(source)
        parsed = reader.parse()
        chunks = chunker(parsed)
        if not chunks:
            print(f"  ⚠ No content extracted, skipping")
            continue
        print(f"  → {len(chunks)} chunks to extract")
        extractor = Extractor(model=model)
        result = extractor.run(chunks)
        # Skip empty/unknown extractions
        if not result or (not result.get("entities") and not result.get("statistics") and not result.get("claims")):
            print(f"  ⚠ No meaningful data extracted, skipping")
            continue
        extractions.append(result)
        print(f"  ✓ Source {i} done")

    if not extractions:
        print("No usable data from any source. Exiting.")
        return

    # Step 4: Analyze and synthesize
    print("Analyzing and synthesizing extracted information...")
    analyzer = Analyzer(model=model, config=config)
    analysis = analyzer.run(extractions)

    # Step 5: Generate report
    print("Generating report...")
    report = reportMaker(model=model, config=config)
    report_path = report.generate(analysis)

    print(f"Report saved to: {report_path}")

if __name__ == "__main__":
    main()