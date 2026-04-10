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
- Produce key_insights proportional to the data density — aim for roughly 1 insight per 2-3 statistics in the extraction, up to {insights_per_source} max
- If the source has very little data (few statistics, short summary), produce fewer insights — do NOT invent or stretch thin data
- A source with 2 statistics should produce 1-2 insights; a source with 20 statistics could produce {insights_per_source}

Source extraction:
"""

CLUSTER_PROMPT = """You are given per-source analyses from multiple documents. Identify pairs or small groups (2-3) of sources that are closely related — they cover the same event, contradict each other, use the same data differently, or directly build on each other.

Return ONLY valid JSON in this exact format:
{{
    "clusters": [
        {{
            "cluster_name": "a descriptive name for this connection (e.g. 'CDC vs WHO Variant Tracking')",
            "sources": ["source_name values of the 2-3 sources in this cluster"],
            "relationship": "1 sentence explaining why these sources are related",
            "relevance": "high|medium|low",
            "shared_entities": ["entities that appear in multiple sources in this cluster"],
            "key_comparison_points": [
                "a specific point of agreement, disagreement, or complementary coverage — write 2-3 sentences with data"
            ]
        }}
    ]
}}

RULES:
- Only cluster sources that have a MEANINGFUL relationship — shared topic is not enough, they must have overlapping data, contradictory claims, or complementary perspectives
- A source can appear in multiple clusters
- Rate relevance: high = directly contradictory or complementary data, medium = same topic with different angles, low = loosely related
- Each cluster must have at least 2 key_comparison_points

Source analyses:
"""

SYNTHESIZE_PROMPT = """You are a senior data analyst. You are given individual analyses from multiple source documents, plus source clusters showing relationships between sources. Your job is to synthesize them into a single unified analysis that forms the blueprint for a report.

Return ONLY valid JSON in this exact format:
{{
    "title": "a descriptive title for a report covering all sources",
    "executive_summary": "{exec_summary_instruction}",
    "narrative_frame": "1 sentence that ties all themes together — NOT a thesis to prove, but an editorial lens to organize the report through",
    "themes": [
        {{
            "theme": "a topic or theme that emerges across sources",
            "insights": ["relevant insights — {section_depth}"],
            "sources_involved": ["source_name values that contributed"]
        }}
    ],
    "source_clusters": {cluster_instruction},
    "cross_source_findings": {cross_source_instruction},
    "visualizations": [
        {{"title": "chart title", "chart_type": "bar|line|pie|hbar|grouped_bar|scatter", "data_points": [{{"label": "x", "value": 0}}], "rationale": "why this chart matters in the overall narrative"}}
    ],
    "narrative_order": ["ordered list of theme names suggesting how the report should flow"],
    "key_takeaways": ["each takeaway must be a full sentence with specific data points — produce exactly {max_takeaways}"]
}}

RULES:
- Produce exactly {max_themes} themes
- executive_summary must be {exec_summary_length}
- Use each source's source_name (not "Source 1" or "Source 2") when referencing sources
- Actively look for connections between sources — shared entities, overlapping time periods, related metrics
- Flag contradictions explicitly with both sides cited
- Merge duplicate visualizations from individual analyses — pick the best version or combine data
- Order the narrative logically: most important themes first, supporting detail after
- If there is only one source, still produce themes and takeaways — set cross_source_findings and source_clusters to empty lists []
- Each key_takeaway must be a full sentence with specific data points, not a vague summary

Source analyses and clusters:
"""

class Analyzer:
    def __init__(self, model=None, config=None):
        self.model = model or Model()
        self.config = config or {}

    def analyze(self, source_extraction):
        prompt = ANALYZE_PROMPT.replace(
            "{insights_per_source}", str(self.config.get("insights_per_source", 5))
        )
        return self.model.call(prompt + json.dumps(source_extraction, indent=2))

    def cluster(self, analyses):
        return self.model.call(CLUSTER_PROMPT + json.dumps(analyses, indent=2))

    def synthesize(self, analyses, clusters):
        include_clusters = self.config.get("include_clusters", False)
        cluster_threshold = self.config.get("cluster_threshold", "high")
        include_cross = self.config.get("include_cross_source", True)

        # Filter clusters by relevance threshold
        if clusters and include_clusters:
            thresholds = {"high": ["high"], "medium": ["high", "medium"], "low": ["high", "medium", "low"]}
            allowed = thresholds.get(cluster_threshold, ["high"])
            filtered = [c for c in clusters.get("clusters", []) if c.get("relevance") in allowed]
            cluster_instruction = json.dumps(filtered)
        else:
            cluster_instruction = "[]"

        cross_source_instruction = '[{"finding": "...", "type": "connection|contradiction|corroboration", "sources": ["..."]}]' if include_cross else "[]"

        prompt = SYNTHESIZE_PROMPT.format(
            max_themes=self.config.get("max_themes", 5),
            max_takeaways=self.config.get("max_takeaways", 5),
            exec_summary_instruction=self.config.get("exec_summary", "2-3 paragraphs") + " covering the most important findings across all sources",
            exec_summary_length=self.config.get("exec_summary", "2-3 paragraphs"),
            section_depth=self.config.get("section_depth", "1 paragraph per point"),
            cluster_instruction=cluster_instruction,
            cross_source_instruction=cross_source_instruction,
        )
        return self.model.call(prompt + json.dumps({"analyses": analyses, "clusters": clusters}, indent=2))

    def _group_by_clusters(self, analyses, clusters):
        """Group analyses using cluster relationships so related sources stay together."""
        if not clusters or not clusters.get("clusters"):
            # No clusters — split into groups of 3
            return [analyses[i:i+3] for i in range(0, len(analyses), 3)]

        # Build a name→analysis lookup
        by_name = {}
        for a in analyses:
            name = a.get("source_name", "")
            by_name[name] = a

        used = set()
        groups = []

        # Group by clusters first
        for c in clusters.get("clusters", []):
            group = []
            for src_name in c.get("sources", []):
                if src_name in by_name and src_name not in used:
                    group.append(by_name[src_name])
                    used.add(src_name)
            if group:
                groups.append(group)

        # Remaining analyses that weren't in any cluster
        remaining = [a for a in analyses if a.get("source_name", "") not in used]
        if remaining:
            for i in range(0, len(remaining), 3):
                groups.append(remaining[i:i+3])

        return groups

    def synthesize_map_reduce(self, analyses, clusters):
        """Map-reduce synthesis: synthesize in groups, then synthesize the sub-results."""
        max_per_group = 3

        if len(analyses) <= max_per_group:
            return self.synthesize(analyses, clusters)

        # Group analyses using cluster info
        groups = self._group_by_clusters(analyses, clusters)

        # Map: synthesize each group
        sub_syntheses = []
        for group in groups:
            sub = self.synthesize(group, clusters)
            sub_syntheses.append(sub)

        # Reduce: if we still have too many sub-syntheses, recurse
        if len(sub_syntheses) > max_per_group:
            # Wrap sub-syntheses as pseudo-analyses for the next round
            wrapped = []
            for s in sub_syntheses:
                wrapped.append({
                    "source_name": s.get("title", "Sub-synthesis"),
                    "source_summary": s.get("executive_summary", ""),
                    "key_insights": [{"insight": t.get("theme", "") + ": " + "; ".join(t.get("insights", [])), "supporting_stats": [], "significance": "high"} for t in s.get("themes", [])],
                    "trends": [],
                    "notable_claims": [],
                    "suggested_visuals": s.get("visualizations", []),
                    "unanswered_questions": [],
                })
            return self.synthesize_map_reduce(wrapped, None)

        # Final reduce: synthesize all sub-syntheses together
        wrapped = []
        for s in sub_syntheses:
            wrapped.append({
                "source_name": s.get("title", "Sub-synthesis"),
                "source_summary": s.get("executive_summary", ""),
                "key_insights": [{"insight": t.get("theme", "") + ": " + "; ".join(t.get("insights", [])), "supporting_stats": [], "significance": "high"} for t in s.get("themes", [])],
                "trends": [],
                "notable_claims": [],
                "suggested_visuals": s.get("visualizations", []),
                "unanswered_questions": [],
            })
        return self.synthesize(wrapped, clusters)

    def run(self, extractions):
        # Phase 1: per-source analysis
        analyses = [self.analyze(ext) for ext in extractions]

        # Phase 2: cluster related sources (only if multiple sources)
        clusters = None
        if len(analyses) > 1 and self.config.get("include_clusters", False):
            clusters = self.cluster(analyses)

        # Phase 3: cross-source synthesis (map-reduce for large source sets)
        synthesis = self.synthesize_map_reduce(analyses, clusters)

        return {
            "per_source": analyses,
            "clusters": clusters,
            "synthesis": synthesis
        }