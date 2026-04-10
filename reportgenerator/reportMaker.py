import json
import os
from datetime import date

REPORT_PROMPT = """You are a report layout assistant. You are given a pre-analyzed JSON blueprint containing insights, themes, visualizations, and takeaways. Your ONLY job is to format this into a valid Quarto (.qmd) document. Do NOT re-analyze or reinterpret the data — just present what you are given.

The output MUST be valid Quarto markdown. NEVER use placeholder text like [2-3 paragraphs here] or [synthesize findings].

---
title: "{{title from synthesis}}"
author: "Report Generator"
date: "{date}"
format:
  {output_format}:
    theme: darkly
    toc: false
    number-sections: true
    embed-resources: true
execute:
  echo: false
  warning: false
---

## Executive Summary

Expand the synthesis executive_summary into {exec_summary}. Each paragraph should be 4-5 sentences. Include specific numbers, dates, and entity names from the data. Do NOT write vague one-liners. Use the narrative_frame as the organizing lens for the summary.

{per_source_section}

## Themes

For EACH theme in synthesis.themes, create a subsection:
### [theme name]
- Write the insights as detailed narrative prose — {section_depth}
- If the theme has related visualizations (from synthesis.visualizations matching this theme), place a ```{{python}} code block here that builds the chart using the EXACT data_points provided, then REMOVE that visualization from the remaining pool so it is NOT repeated later
- Reference sources by their actual name, never as "Source 1" or "Source 2"

{cluster_section}

{cross_source_section}

## Visualizations

Only include visualizations here that were NOT already placed inside a theme section above. If all visualizations were already placed in themes, skip this section entirely. Do NOT duplicate any chart.
```{{python}}
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Use the EXACT data_points from the visualization spec
# chart_type tells you what kind of chart to make:
#   bar → plt.bar / sns.barplot
#   hbar → plt.barh
#   line → plt.plot
#   pie → plt.pie
#   grouped_bar → side-by-side bars
#   scatter → plt.scatter
# Use the visualization title as plt.title()
```

## Key Takeaways

Present synthesis.key_takeaways as a numbered list. Expand each takeaway into 2-3 sentences with specific data points and context. {section_depth}

--RULES FOR WRITING THE REPORT (do not include these rules in the final report):
CRITICAL FORMATTING RULES:
- Start with --- YAML frontmatter ---
- Use the title from synthesis.title in the frontmatter
- Use ## for section headers, ### for subsections
- Use ```{{python}} for executable code blocks
- Do NOT use plain text headers like "Executive Summary:" — always use ## markdown headers
- Do NOT add analysis or interpretation beyond what the blueprint provides
- Follow synthesis.narrative_order for the ordering of theme sections

VISUALIZATION RULES:
- Use the EXACT data_points from each visualization spec — do not invent data
- Use plt.tight_layout() before plt.show() to prevent label cutoff
- Use horizontal bar charts (plt.barh) when labels are long
- Use separate ```{{python}} code blocks for separate visualizations
- Add the visualization title and axis labels to every chart
- Use seaborn (sns) for cleaner styling when possible
- Set figure size with plt.figure(figsize=(10, 6)) for readability
- Use the chart_type field to determine the visualization type
- NEVER create a chart where ALL values are zero — skip that visualization entirely
- NEVER use placeholder labels like 'Category 1', 'Category 2', etc. — every label must be a real, descriptive name from the data
- NEVER invent fake data_points. If the visualization spec has no meaningful data, skip it
- If a source has no extractable data or is labeled 'Unknown', skip it entirely — do not write a section for it

Return ONLY the raw .qmd content. No wrapping, no explanation.

Analysis blueprint:
"""

PER_SOURCE_SECTION = """## Source Deep-Dives

For EACH item in per_source, create a subsection:
### [source_name]
- Write the source_summary as an intro paragraph
- Expand each key_insight into a detailed paragraph — {section_depth}
- Include notable_claims with their strength ratings and reasoning
- Include trends as a narrative paragraph
- If suggested_visuals exist for this source, create ```{{python}} code blocks using the EXACT data_points
"""

CLUSTER_SECTION = """## Source Connections

For EACH item in synthesis.source_clusters, create a subsection:
### [cluster_name]
- Explain the relationship between the sources in this cluster
- Write each key_comparison_point as a full paragraph — {section_depth}
- Reference the specific sources by name
- Highlight agreements, disagreements, and complementary perspectives
"""

CROSS_SOURCE_SECTION = """## Cross-Source Findings

For each item in synthesis.cross_source_findings:
- State the finding as a full paragraph with context
- Label it as a connection, contradiction, or corroboration
- Reference the sources by name
(If cross_source_findings is empty, skip this section entirely)
"""

SECTION_PROMPT = """You are a report layout assistant writing ONE section of a Quarto (.qmd) report. Do NOT include YAML frontmatter. Do NOT include sections other than the one requested. Write ONLY the requested section content.

RULES:
- Use ## for section headers, ### for subsections
- Use ```{{python}} for executable code blocks
- Reference sources by their actual name, never as "Source 1" or "Source 2"
- Do NOT use placeholder text — write real, detailed content
- {section_depth}

VISUALIZATION RULES (if applicable):
- Use the EXACT data_points from visualization specs — do not invent data
- NEVER create a chart where ALL values are zero — skip that visualization entirely
- NEVER use placeholder labels like 'Category 1', 'Category 2', etc. — every label must be a real, descriptive name from the data
- NEVER invent fake data_points. If the visualization spec has no meaningful data, skip it
- If a source is labeled 'Unknown' or has no real data, skip it entirely
- Use plt.tight_layout() before plt.show()
- Use horizontal bar charts (plt.barh) when labels are long
- Use separate ```{{python}} code blocks for separate visualizations
- Set figure size with plt.figure(figsize=(10, 6))
- Use seaborn (sns) for cleaner styling

Write this section now:
{section_instruction}

Data:
"""

class reportMaker:
    def __init__(self, model=None, output_dir="reports", config=None):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.model = model
        self.output_dir = output_dir
        self.config = config or {}

    def _fix_qmd(self, content):
        # Ensure frontmatter delimiters exist
        if not content.startswith("---"):
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if line.strip() == "" and i > 0:
                    lines.insert(0, "---")
                    lines.insert(i + 1, "---")
                    break
            content = "\n".join(lines)
        return content

    def _build_frontmatter(self, analysis, output_format):
        title = analysis.get("synthesis", {}).get("title", "Report")
        return f"""---
title: "{title}"
author: "Report Generator"
date: "{date.today().isoformat()}"
format:
  {output_format}:
    theme: darkly
    toc: true
    toc-depth: 2
    number-sections: true
    embed-resources: true
execute:
  echo: false
  warning: false
---
"""

    def _generate_section(self, instruction, data, depth):
        prompt = SECTION_PROMPT.format(
            section_depth=depth,
            section_instruction=instruction,
        ) + json.dumps(data, indent=2)
        return self.model.call_raw(prompt)

    def _generate_single_call(self, analysis, output_format):
        """Original single-call generation for brief/standard modes."""
        depth = self.config.get("section_depth", "1 paragraph per point")

        per_source = ""
        if self.config.get("include_per_source_sections", False):
            per_source = PER_SOURCE_SECTION.format(section_depth=depth)

        cluster = ""
        if self.config.get("include_clusters", False) and analysis.get("clusters"):
            cluster = CLUSTER_SECTION.format(section_depth=depth)

        cross_source = ""
        if self.config.get("include_cross_source", True):
            cross_source = CROSS_SOURCE_SECTION

        prompt = REPORT_PROMPT.format(
            output_format=output_format,
            date=date.today().isoformat(),
            exec_summary=self.config.get("exec_summary", "2-3 paragraphs"),
            section_depth=depth,
            per_source_section=per_source,
            cluster_section=cluster,
            cross_source_section=cross_source,
        ) + json.dumps(analysis, indent=2)
        return self.model.call_raw(prompt)

    def _generate_sectioned(self, analysis, output_format):
        """Section-by-section generation for detailed mode — avoids hitting output token limits."""
        depth = self.config.get("section_depth", "2-3 paragraphs per point with examples, context, and implications")
        synthesis = analysis.get("synthesis", {})
        per_source = analysis.get("per_source", [])
        sections = []

        # Frontmatter
        sections.append(self._build_frontmatter(analysis, output_format))

        # Executive Summary
        sections.append(self._generate_section(
            f"Write ## Executive Summary. Expand this into {self.config.get('exec_summary', '3-4 paragraphs')}. "
            "Each paragraph should be 4-5 sentences with specific numbers, dates, and entity names.",
            {"executive_summary": synthesis.get("executive_summary", ""), "narrative_frame": synthesis.get("narrative_frame", "")},
            depth
        ))

        # Per-source deep-dives
        if self.config.get("include_per_source_sections", False) and per_source:
            # Filter out unknown/empty sources
            valid_sources = [src for src in per_source if src.get("source_name", "").lower() not in ("unknown", "unknown source", "")]
            if valid_sources:
                sections.append("\n## Source Deep-Dives\n")
                for src in valid_sources:
                    sections.append(self._generate_section(
                        f"Write ### {src.get('source_name', 'Source')} deep-dive. "
                        "Write source_summary as an intro paragraph, expand each key_insight into a detailed paragraph, "
                        "include notable_claims with strength ratings, include trends as narrative, "
                        "and create ```{python} code blocks for any suggested_visuals using EXACT data_points. "
                        "Do NOT create charts where all values are zero. Do NOT use placeholder labels like 'Category 1'.",
                        src, depth
                    ))

        # Themes
        themes = synthesis.get("themes", [])
        visuals = synthesis.get("visualizations", [])
        if themes:
            for ti, theme in enumerate(themes):
                # Find matching visualizations for this theme
                theme_visuals = [v for v in visuals if theme.get("theme", "").lower() in v.get("rationale", "").lower() or theme.get("theme", "").lower() in v.get("title", "").lower()]
                if ti == 0:
                    # First theme includes the ## Themes header
                    sections.append(self._generate_section(
                        f"Write ## Themes as the section header, then write ### {theme.get('theme', '')} as the first subsection under it. "
                        "Write each insight as detailed narrative prose paragraphs (NOT as ### headers). "
                        "Use ### ONLY for the subsection title. Body text must be normal paragraphs. "
                        "Reference sources by name. "
                        "If visualizations are provided, create ```{python} code blocks using EXACT data_points.",
                        {"theme": theme, "visualizations": theme_visuals},
                        depth
                    ))
                else:
                    sections.append(self._generate_section(
                        f"Write ### {theme.get('theme', '')} subsection. "
                        "Write each insight as detailed narrative prose paragraphs (NOT as ### headers). "
                        "Use ### ONLY for the subsection title. Body text must be normal paragraphs. "
                        "Reference sources by name. "
                        "If visualizations are provided, create ```{python} code blocks using EXACT data_points.",
                        {"theme": theme, "visualizations": theme_visuals},
                        depth
                    ))

        # Source Connections (clusters)
        clusters = analysis.get("clusters")
        if self.config.get("include_clusters", False) and clusters:
            source_clusters = synthesis.get("source_clusters", [])
            if source_clusters:
                sections.append(self._generate_section(
                    "Write ## Source Connections. For each cluster, create a ### subsection explaining "
                    "the relationship, writing each comparison point as a full paragraph, referencing sources by name.",
                    {"source_clusters": source_clusters},
                    depth
                ))

        # Cross-Source Findings
        cross = synthesis.get("cross_source_findings", [])
        if self.config.get("include_cross_source", True) and cross:
            sections.append(self._generate_section(
                "Write ## Cross-Source Findings. For each finding, write a full paragraph with context, "
                "label as connection/contradiction/corroboration, reference sources by name.",
                {"cross_source_findings": cross},
                depth
            ))

        # Remaining visualizations not placed in themes
        remaining_visuals = [v for v in visuals if not any(
            theme.get("theme", "").lower() in v.get("rationale", "").lower() or theme.get("theme", "").lower() in v.get("title", "").lower()
            for theme in themes
        )]
        if remaining_visuals:
            sections.append(self._generate_section(
                "Write ## Additional Visualizations. Create ```{python} code blocks for each visualization using EXACT data_points. "
                "Do NOT duplicate any charts already generated in previous sections.",
                {"visualizations": remaining_visuals},
                depth
            ))

        # Key Takeaways
        takeaways = synthesis.get("key_takeaways", [])
        if takeaways:
            sections.append(self._generate_section(
                "Write ## Key Takeaways as a numbered list. Expand each takeaway into 2-3 sentences with specific data points.",
                {"key_takeaways": takeaways},
                depth
            ))

        return "\n\n".join(sections)

    def generate(self, analysis, report_name="report", output_format="html"):
        if self.config.get("sectioned_generation", False):
            # Multi-page: section-by-section to avoid output token limits
            qmd_content = self._fix_qmd(self._generate_sectioned(analysis, output_format))
        else:
            # Brief: single call
            qmd_content = self._fix_qmd(self._generate_single_call(analysis, output_format))

        output_path = os.path.join(self.output_dir, f"{report_name}.qmd")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(qmd_content)
        
        return output_path