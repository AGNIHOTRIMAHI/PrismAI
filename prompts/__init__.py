"""
prompts/__init__.py — All LangChain prompt templates for the PR review agents.
"""

from langchain_core.prompts import ChatPromptTemplate

# ── CRAG Grader Prompt ────────────────────────────────────────────────────────
CRAG_GRADER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are a relevance grader. Given a query and a document, "
            "return ONLY valid JSON with a single key 'score' (float 0.0-1.0). "
            "1.0 = highly relevant, 0.0 = completely irrelevant. "
            "No markdown, no explanation — just JSON."
        ),
    ),
    ("human", "Query: {query}\n\nDocument:\n{document}"),
])

# ── Security Agent Prompt ──────────────────────────────────────────────────────
SECURITY_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are an expert application security engineer specialising in "
            "secure code review. You know OWASP Top 10, CWE, and secure coding "
            "best practices deeply.\n\nRelevant knowledge context:\n{crag_context}"
        ),
    ),
    (
        "human",
        (
            "Review this Pull Request for security vulnerabilities.\n\n"
            "PR Title: {pr_title}\nAuthor: {pr_author}\nFiles Changed: {files_changed}\n\n"
            "```diff\n{diff_context}\n```\n\n"
            "Provide a structured security review covering:\n"
            "1. Critical vulnerabilities\n2. High severity issues\n"
            "3. Medium severity issues\n4. Recommendations\n\n"
            "End with: **Security Score: X/10** (10 = most severe risk)"
        ),
    ),
])

# ── Performance Agent Prompt ───────────────────────────────────────────────────
PERFORMANCE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are an expert software performance engineer specialising in "
            "algorithmic inefficiencies, database anti-patterns, and scalability.\n\n"
            "Relevant knowledge context:\n{crag_context}"
        ),
    ),
    (
        "human",
        (
            "Review this Pull Request for performance issues.\n\n"
            "PR Title: {pr_title}\nAuthor: {pr_author}\nFiles Changed: {files_changed}\n\n"
            "```diff\n{diff_context}\n```\n\n"
            "Analyse for: algorithm complexity, N+1 queries, unbounded fetches, "
            "memory leaks, missing caching, blocking I/O.\n\n"
            "End with: **Performance Score: X/10** (10 = most severe bottleneck)"
        ),
    ),
])

# ── Style Agent Prompt ─────────────────────────────────────────────────────────
STYLE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are an expert software engineer focused on code quality, "
            "maintainability, and clean code principles.\n\n"
            "Relevant knowledge context:\n{crag_context}"
        ),
    ),
    (
        "human",
        (
            "Review this Pull Request for code style and quality issues.\n\n"
            "PR Title: {pr_title}\nAuthor: {pr_author}\nFiles Changed: {files_changed}\n\n"
            "```diff\n{diff_context}\n```\n\n"
            "Analyse for: naming, function size, DRY violations, error handling, "
            "type annotations, dead code, test coverage gaps.\n\n"
            "End with: **Quality Score: X/10** (10 = most severe quality issues)"
        ),
    ),
])

# ── Aggregator Prompt ──────────────────────────────────────────────────────────
AGGREGATOR_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are a senior staff engineer writing a comprehensive PR review comment for GitHub. "
            "Write in GitHub-flavoured Markdown. Be constructive, specific, and actionable. "
            "Use tables, badges, and emojis to make the review visually clear and scannable. "
            "Never write walls of text — use structured sections with clear headings."
        ),
    ),
    (
        "human",
        (
            "Synthesise these specialist reviews into one polished GitHub PR comment.\n\n"
            "**PR Details**\n"
            "Title: {pr_title}\n"
            "Author: @{pr_author}\n"
            "Files Changed: {files_changed}\n"
            "Diff: +{additions} additions / -{deletions} deletions\n"
            "Security Score: {security_score}/10\n\n"
            "---\n"
            "**Security Review**\n{security_report}\n\n"
            "**Performance Review**\n{performance_report}\n\n"
            "**Style & Quality Review**\n{style_report}\n\n"
            "---\n\n"
            "Generate a GitHub PR comment using EXACTLY this structure:\n\n"

            "---\n"
            "## 🛡️ PrismAI — Automated Code Review\n\n"

            "> Use a single line summary of what this PR does based on the title.\n\n"

            "---\n\n"
            "## 📊 Review Scorecard\n\n"
            "| Category | Score | Status |\n"
            "| --- | --- | --- |\n"
            "| 🔐 Security | X/10 | 🔴 Critical / 🟡 Warning / 🟢 Safe |\n"
            "| ⚡ Performance | X/10 | 🔴 / 🟡 / 🟢 |\n"
            "| 🎨 Style & Quality | X/10 | 🔴 / 🟡 / 🟢 |\n\n"

            "Use these rules for status emoji: score 8-10 = 🔴 Critical, 4-7 = 🟡 Warning, 0-3 = 🟢 Safe\n\n"

            "---\n\n"
            "## 🚨 Critical Issues — Must Fix Before Merge\n\n"
            "For each critical issue use this format:\n"
            "#### ⛔ [Issue Title]\n"
            "- **File:** `filename` (Line X)\n"
            "- **Problem:** Clear description\n"
            "- **Fix:** Specific actionable recommendation\n\n"
            "If no critical issues write: > ✅ No critical issues found.\n\n"

            "---\n\n"
            "## ⚠️ Important Improvements — Should Fix\n\n"
            "For each important issue use this format:\n"
            "#### 🟡 [Issue Title]\n"
            "- **File:** `filename`\n"
            "- **Problem:** Description\n"
            "- **Fix:** Recommendation\n\n"
            "If none write: > ✅ No important improvements needed.\n\n"

            "---\n\n"
            "## 💡 Minor Suggestions — Nice to Have\n\n"
            "Use a simple bullet list for minor suggestions. Keep each under 2 lines.\n\n"

            "---\n\n"
            "## 🏁 Merge Verdict\n\n"
            "Use EXACTLY one of these three verdicts based on security_score:\n\n"
            "If security_score >= 7:\n"
            "> ### 🔴 BLOCKED — Changes Required\n"
            "> Critical security issues must be resolved before this PR can be merged.\n\n"
            "If security_score >= 4:\n"
            "> ### 🟡 HOLD — Review Recommended\n"
            "> Important issues should be addressed. A senior engineer will review via HITL gate.\n\n"
            "If security_score < 4:\n"
            "> ### 🟢 APPROVED — Safe to Merge\n"
            "> No critical issues found. This PR meets the required quality standards.\n\n"

            "---\n\n"
            "_🤖 Review generated by [PrismAI](https://github.com) · "
            "Powered by Gemini · "
            "⏱️ {pr_author} · Multi-Agent Pipeline (Security + Performance + Style)_\n"
        ),
    ),
])