"""Convert the markdown guide to a styled PDF."""
import markdown
from weasyprint import HTML

INPUT_FILE = "complete-guide.md"
OUTPUT_FILE = "/output/Apartment_Monitor_Complete_Guide.pdf"

CSS = """
@page {
    size: A4;
    margin: 2cm;
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9px;
        color: #888;
    }
}
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 11px;
    line-height: 1.6;
    color: #1a1a1a;
    max-width: 100%;
}
h1 {
    color: #1a1a2e;
    border-bottom: 3px solid #16213e;
    padding-bottom: 8px;
    font-size: 24px;
    margin-top: 30px;
    page-break-before: auto;
}
h2 {
    color: #16213e;
    border-bottom: 1px solid #ccc;
    padding-bottom: 5px;
    font-size: 18px;
    margin-top: 25px;
    page-break-before: always;
}
h2:first-of-type {
    page-break-before: avoid;
}
h3 {
    color: #0f3460;
    font-size: 14px;
    margin-top: 20px;
}
h4 {
    color: #333;
    font-size: 12px;
    margin-top: 15px;
}
code {
    background-color: #f0f0f0;
    padding: 1px 4px;
    border-radius: 3px;
    font-family: "SF Mono", "Menlo", "Monaco", "Courier New", monospace;
    font-size: 10px;
}
pre {
    background-color: #1e1e2e;
    color: #cdd6f4;
    padding: 12px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 9.5px;
    line-height: 1.5;
    page-break-inside: avoid;
}
pre code {
    background: none;
    padding: 0;
    color: #cdd6f4;
    font-size: 9.5px;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 10px 0;
    font-size: 10px;
    page-break-inside: avoid;
}
th {
    background-color: #16213e;
    color: white;
    padding: 8px 10px;
    text-align: left;
    font-weight: 600;
}
td {
    padding: 6px 10px;
    border-bottom: 1px solid #ddd;
}
tr:nth-child(even) {
    background-color: #f8f8f8;
}
blockquote {
    border-left: 4px solid #16213e;
    margin: 15px 0;
    padding: 10px 15px;
    background-color: #f8f9fa;
    color: #333;
}
hr {
    border: none;
    border-top: 2px solid #eee;
    margin: 25px 0;
}
a {
    color: #0f3460;
    text-decoration: none;
}
ul, ol {
    padding-left: 20px;
}
li {
    margin-bottom: 3px;
}
"""

with open(INPUT_FILE, "r") as f:
    md_content = f.read()

html_body = markdown.markdown(
    md_content,
    extensions=["tables", "fenced_code", "toc", "nl2br"],
)

html_full = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>{CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""

HTML(string=html_full).write_pdf(OUTPUT_FILE)
print(f"PDF generated: {OUTPUT_FILE}")
