"""Prompt templates for the extraction stage (map-reduce pipeline)."""

# Prompts for the extraction stage (extractor/extractor.py)
# These handle the map-reduce pipeline: each chunk gets individually extracted,
# then results are consolidated via reduce into one extraction per source.

# Sent to the LLM for each text chunk. Asks for structured JSON with
# entities, statistics, claims, and a short summary. Enforces full-year
# dates and specificity in metric descriptions.
EXTRACT_PROMPT = """You are a data extraction assistant. Extract structured information from the following content.

Return ONLY valid JSON in this exact format:
{
    "entities": ["list of key entities, organizations, people mentioned"],
    "statistics": [
        {"metric": "name", "value": 0, "unit": "unit", "measurement_type": "how the number was obtained", "comparison_scope": "what set of things this number belongs to", "context": "full date with year, source, and what the number specifically measures"}
    ],
    "claims": [
        {"statement": "a key claim made", "evidence_quote": "supporting quote from text"}
    ],
    "summary": "2-3 sentence summary of this content"
}

RULES:
- Always include the FULL YEAR in any date (e.g. "September 6, 2021" not "week of Sep 6th")
- Be specific about what each metric measures — include who, what, where, when
- If the source is vague about a date or metric, note that in the context field
- measurement_type MUST describe HOW the number was obtained, using terms from the source when possible. Examples: "confirmed cases", "reported deaths", "seroprevalence", "excess mortality", "self-reported survey", "hospital admissions", "modeled estimate", "age-adjusted rate", "crude rate". If the source does not specify, use "unspecified".
- comparison_scope MUST describe the population or grouping the number belongs to, e.g. "US adults aged 65+", "high-income countries (World Bank classification)", "nationwide, all ages". Two statistics are only directly comparable if they share the same measurement_type AND comparison_scope.
- Do NOT silently normalize numbers across different measurement types (e.g. do not treat "confirmed cases" and "seroprevalence" as the same metric)

Content:
"""

# Used instead of EXTRACT_PROMPT when a chunk is tagged as a table.
# Same output schema, but the input is serialized table data.
TABLE_PROMPT = """You are a data extraction assistant. Analyze this table data and extract key statistics and insights.

Return ONLY valid JSON in the same format as above.

Table data:
"""

# Used during the reduce step to merge multiple chunk extractions into one.
# Deduplicates entities, merges stats, keeps only well-supported claims,
# and writes a single document-level summary.
REDUCE_PROMPT = """You are given extractions from multiple chunks of the same document.
Consolidate into a single extraction:
- Deduplicate entities
- Merge statistics (flag contradictions)
- Preserve the `measurement_type` and `comparison_scope` fields on every statistic; never drop or blank them during merging
- Only merge two statistics into one if they share the same `measurement_type` AND `comparison_scope` (otherwise keep them as separate entries)
- Keep only well-supported claims
- Write one overall document summary

Return ONLY valid JSON in the same structured format.

Chunk extractions:
"""
