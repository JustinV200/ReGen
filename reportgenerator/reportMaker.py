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
execute:
  echo: false
  warning: false
---

## Executive Summary

Expand the synthesis executive_summary into 2-3 SUBSTANTIAL paragraphs. Each paragraph should be 4-5 sentences. Include specific numbers, dates, and entity names from the data. Do NOT write vague one-liners.

## Themes

For EACH theme in synthesis.themes, create a subsection:
### [theme name]
- Write the insights as detailed narrative prose — expand each insight into a full paragraph with context and explanation
- If the theme has related visualizations (from synthesis.visualizations matching this theme), place a ```{{python}} code block here that builds the chart using the EXACT data_points provided, then REMOVE that visualization from the remaining pool so it is NOT repeated later
- Reference sources by their actual name, never as "Source 1" or "Source 2"

## Cross-Source Findings

For each item in synthesis.cross_source_findings:
- State the finding as a full paragraph with context
- Label it as a connection, contradiction, or corroboration
- Reference the sources by name
(If cross_source_findings is empty, skip this section entirely)

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

Present synthesis.key_takeaways as a numbered list. Expand each takeaway into 2-3 sentences with specific data points and context. Do NOT just repeat the takeaway verbatim — elaborate on its significance.

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

Return ONLY the raw .qmd content. No wrapping, no explanation.

Analysis blueprint:
"""

class reportMaker:
    def __init__(self, model = None, output_dir = "reports"):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.model = model
        self.output_dir = output_dir

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

    def generate(self, analysis, report_name="report", output_format="html"):
        prompt = REPORT_PROMPT.format(output_format=output_format, date=date.today().isoformat()) + json.dumps(analysis, indent=2)
        qmd_content = self._fix_qmd(self.model.call_raw(prompt))
        output_path = os.path.join(self.output_dir, f"{report_name}.qmd")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(qmd_content)
        
        return output_path