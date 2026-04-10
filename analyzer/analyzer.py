import json

from extractor import Model


ANALYZE_PROMPT = """You are a data analyst. You are given a structured extraction (entities, statistics, claims, summary) from a single source document. Your job is NOT to re-extract — all the facts are already provided. Your job is to INTERPRET the data.

Return ONLY valid JSON in this exact format:
{
    "source_summary": "1 sentence identifying this source",
    "source_name": "a short descriptive name for this source (e.g. 'USA Today COVID-19 Report, Sep 2025')",
    "key_insights": [
        {"insight": "a meaningful interpretation of the data — write 2-3 full sentences explaining what the data means, why it matters, and what it implies", "supporting_stats": ["metric names that support this"], "significance": "high|medium|low"}
    ],
    "trends": ["any patterns, increases, decreases, or trajectories in the data"],
    "notable_claims": [
        {"claim": "the claim", "strength": "strong|moderate|weak", "reasoning": "why you rated it this way"}
    ],
    "suggested_visuals": [
        {"title": "chart title", "chart_type": "bar|line|pie|hbar|grouped_bar|scatter", "data_points": [{"label": "x", "value": 0}], "rationale": "why this visualization is useful"}
    ],
    "unanswered_questions": ["gaps or things the source doesn't address"]
}

RULES:
- Only suggest a visualization if 3+ related data points exist for it
- Do NOT put unrelated metrics in the same visualization
- Rate insight significance based on magnitude, novelty, and actionability
- Flag any statistics that seem implausible or lack context
- Keep all dates with full year

Source extraction:
"""

SYNTHESIZE_PROMPT = """You are a senior data analyst. You are given individual analyses from multiple source documents. Your job is to synthesize them into a single unified analysis that forms the blueprint for a report.

Return ONLY valid JSON in this exact format:
{
    "title": "a descriptive title for a report covering all sources",
    "executive_summary": "3-4 sentences covering the most important findings across all sources",
    "themes": [
        {
            "theme": "a topic or theme that emerges across sources",
            "insights": ["relevant insights from any source that relate to this theme"],
            "sources_involved": ["which source summaries contributed"]
        }
    ],
    "cross_source_findings": [
        {"finding": "a connection, contradiction, or corroboration between sources", "type": "connection|contradiction|corroboration", "sources": ["source summaries involved"]}
    ],
    "visualizations": [
        {"title": "chart title", "chart_type": "bar|line|pie|hbar|grouped_bar|scatter", "data_points": [{"label": "x", "value": 0}], "rationale": "why this chart matters in the overall narrative"}
    ],
    "narrative_order": ["ordered list of theme names suggesting how the report should flow"],
    "key_takeaways": ["3-5 top-level conclusions a reader should walk away with"]
}

RULES:
- Actively look for connections between sources — shared entities, overlapping time periods, related metrics
- Flag contradictions explicitly with both sides cited
- Merge duplicate visualizations from individual analyses — pick the best version or combine data
- Order the narrative logically: most important themes first, supporting detail after
- If there is only one source, still produce themes and takeaways — set cross_source_findings to an empty list []
- Use each source's source_name (not "Source 1" or "Source 2") when referencing sources
- executive_summary must be at least 4 substantial sentences
- Each key_takeaway must be a full sentence with specific data points, not a vague summary

Source analyses:
"""
class Analyzer:
    def __init__(self, model=None):
        self.model = model or Model()

    def analyze(self, source_extraction):
        return self.model.call(ANALYZE_PROMPT + json.dumps(source_extraction, indent=2))

    def synthesize(self, analyses):
        return self.model.call(SYNTHESIZE_PROMPT + json.dumps(analyses, indent=2))

    def run(self, extractions):
        # Phase 1: per-source analysis
        analyses = [self.analyze(ext) for ext in extractions]

        # Phase 2: cross-source synthesis
        synthesis = self.synthesize(analyses)

        return {
            "per_source": analyses,
            "synthesis": synthesis
        }