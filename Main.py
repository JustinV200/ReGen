from dotenv import load_dotenv
load_dotenv()

from input_processing import Reader, chunker
from extractor import Model, Extractor
from analyzer import Analyzer
from reportgenerator import reportMaker

def main():
    sources = [
        "https://www.usatoday.com/story/news/health/2025/09/15/covid-19-september-2025-cases-variants-symptoms-vaccines/86163707007/",
        "https://www.cdc.gov/covid/php/surveillance/index.html"
    ]

    model = Model()

    # Step 1-3: For each source, read, parse, chunk, and extract
    extractions = []
    for source in sources:
        reader = Reader(source)
        parsed = reader.parse()
        chunks = chunker(parsed)
        extractor = Extractor(model=model)
        extractions.append(extractor.run(chunks))

    # Step 4: Analyze and synthesize
    analyzer = Analyzer(model=model)
    analysis = analyzer.run(extractions)

    # Step 5: Generate report
    report = reportMaker(model=model)
    report_path = report.generate(analysis)

    print(f"Report saved to: {report_path}")

if __name__ == "__main__":
    main()