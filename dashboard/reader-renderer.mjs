import { katex } from "./vendor/katex/katex.js";

"use strict";

export function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderMath(tex, displayMode, source) {
  if (!tex.trim()) return escapeHTML(source);
  try {
    const rendered = katex.renderToString(tex, {
      displayMode,
      throwOnError: true,
      strict: "ignore",
      trust: false,
      maxSize: 30,
      maxExpand: 1000,
      output: "htmlAndMathml",
    });
    return displayMode
      ? `<div class="math-block">${rendered}</div>`
      : `<span class="math-inline">${rendered}</span>`;
  } catch (error) {
    const message = escapeHTML(error.message);
    return displayMode
      ? `<pre class="math-fallback math-fallback-block" data-math-error="true" title="${message}">${escapeHTML(source)}</pre>`
      : `<span class="math-fallback" data-math-error="true" title="${message}">${escapeHTML(source)}</span>`;
  }
}

function isEscaped(text, index) {
  let backslashes = 0;
  for (let cursor = index - 1; cursor >= 0 && text[cursor] === "\\"; cursor -= 1) {
    backslashes += 1;
  }
  return backslashes % 2 === 1;
}

function parseInlineMath(text, start) {
  if (text.startsWith("\\(", start)) {
    const end = text.indexOf("\\)", start + 2);
    if (end >= 0) {
      const source = text.slice(start, end + 2);
      return {
        html: renderMath(text.slice(start + 2, end), false, source),
        end: end + 2,
      };
    }
  }

  if (text[start] !== "$" || text[start + 1] === "$" || isEscaped(text, start)) return null;
  for (let cursor = start + 1; cursor < text.length; cursor += 1) {
    if (text[cursor] !== "$" || text[cursor + 1] === "$" || isEscaped(text, cursor)) continue;
    const source = text.slice(start, cursor + 1);
    return {
      html: renderMath(text.slice(start + 1, cursor), false, source),
      end: cursor + 1,
    };
  }
  return null;
}

function parseDisplayMath(lines, start) {
  const first = lines[start].trim();
  const opener = first.startsWith("$$") ? "$$" : "\\[";
  const closer = opener === "$$" ? "$$" : "\\]";
  const body = [];
  let current = first.slice(opener.length);
  let index = start;

  if (current.endsWith(closer)) {
    body.push(current.slice(0, -closer.length));
    return {
      html: renderMath(body.join("\n"), true, first),
      next: start + 1,
    };
  }

  body.push(current);
  index += 1;
  while (index < lines.length) {
    current = lines[index].trimEnd();
    if (current.endsWith(closer)) {
      body.push(current.slice(0, -closer.length));
      const source = [lines[start], ...lines.slice(start + 1, index + 1)].join("\n");
      return {
        html: renderMath(body.join("\n"), true, source),
        next: index + 1,
      };
    }
    body.push(lines[index]);
    index += 1;
  }

  const source = lines.slice(start).join("\n");
  return {
    html: `<pre class="math-fallback">${escapeHTML(source)}</pre>`,
    next: lines.length,
  };
}

function parseInlineLink(text, start) {
  let labelEnd = start + 1;
  let labelDepth = 1;
  let labelEscaped = false;
  while (labelEnd < text.length && labelDepth > 0) {
    const char = text[labelEnd];
    if (!labelEscaped) {
      if (char === "[") labelDepth += 1;
      if (char === "]") labelDepth -= 1;
    }
    labelEscaped = char === "\\" && !labelEscaped;
    if (char !== "\\") labelEscaped = false;
    labelEnd += 1;
  }
  if (labelDepth !== 0 || text[labelEnd] !== "(") return null;
  labelEnd -= 1;
  let cursor = labelEnd + 2;
  let depth = 1;
  let escaped = false;
  while (cursor < text.length) {
    const char = text[cursor];
    if (!escaped) {
      if (char === "(") depth += 1;
      if (char === ")") {
        depth -= 1;
        if (depth === 0) break;
      }
    }
    escaped = char === "\\" && !escaped;
    if (char !== "\\") escaped = false;
    cursor += 1;
  }
  if (depth !== 0) return null;
  return {
    label: text.slice(start + 1, labelEnd),
    target: text.slice(labelEnd + 2, cursor).trim(),
    end: cursor + 1,
  };
}

function localLinkHTML(parsed, label, context) {
  const isDirectDocument = /\.(?:reader\.md|pdf)(?:#.*)?$/i.test(parsed.target);
  if (context?.offline) {
    const resolved = context.resolveLocalLink?.(parsed.target);
    if (!resolved) {
      return `<span class="offline-unavailable-link" title="Not included in this offline package">${label}</span>`;
    }
    const page = resolved.match(/#page=(\d+)/i)?.[1];
    const hint = page && context.showPdfPageHints
      ? `<span class="pdf-page-hint" aria-label="PDF page ${escapeHTML(page)}">p.${escapeHTML(page)}</span>`
      : "";
    return `<a class="local-file-link" href="${escapeHTML(resolved)}" target="_blank" rel="noopener">${label}${hint}</a>`;
  }
  if (isDirectDocument) {
    const resolved = context?.resolveLocalLink?.(parsed.target);
    if (resolved) {
      return `<a class="local-file-link" href="${escapeHTML(resolved)}" target="_blank" rel="noopener">${label}</a>`;
    }
  }
  return `<button class="local-file-link" type="button" data-file-project="${escapeHTML(context?.project)}" data-file-source="${escapeHTML(context?.source)}" data-file-target="${escapeHTML(parsed.target)}" data-file-new-tab="true">${label}</button>`;
}

export function inlineMarkdown(text, context) {
  let output = "";
  let index = 0;
  while (index < text.length) {
    if (text.startsWith('<a id="', index)) {
      const anchor = text.slice(index).match(/^<a id="([A-Za-z0-9:._-]+)"><\/a>/);
      if (anchor) {
        output += `<span id="${escapeHTML(anchor[1])}" class="markdown-anchor" aria-hidden="true"></span>`;
        index += anchor[0].length;
        continue;
      }
    }
    if (text[index] === "[" && context) {
      const parsed = parseInlineLink(text, index);
      if (parsed) {
        const label = inlineMarkdown(parsed.label, null);
        if (/^#[A-Za-z0-9:._-]+$/.test(parsed.target)) {
          const fragment = parsed.target.slice(1);
          output += `<a class="reader-anchor-link" href="${escapeHTML(parsed.target)}" data-reader-anchor="${escapeHTML(fragment)}">${label}</a>`;
        } else if (/^(https?:|mailto:)/i.test(parsed.target)) {
          output += `<a href="${escapeHTML(parsed.target)}" target="_blank" rel="noopener">${label}</a>`;
        } else {
          output += localLinkHTML(parsed, label, context);
        }
        index = parsed.end;
        continue;
      }
    }
    if (text[index] === "`" && text.indexOf("`", index + 1) > index) {
      const end = text.indexOf("`", index + 1);
      output += `<code>${escapeHTML(text.slice(index + 1, end))}</code>`;
      index = end + 1;
      continue;
    }
    const math = parseInlineMath(text, index);
    if (math) {
      output += math.html;
      index = math.end;
      continue;
    }
    if (text.startsWith("**", index) && text.indexOf("**", index + 2) > index) {
      const end = text.indexOf("**", index + 2);
      output += `<strong>${inlineMarkdown(text.slice(index + 2, end), context)}</strong>`;
      index = end + 2;
      continue;
    }
    if (text[index] === "*" && text[index + 1] !== "*" && !isEscaped(text, index)) {
      let end = index + 1;
      while (end < text.length) {
        if (
          text[end] === "*"
          && text[end - 1] !== "*"
          && text[end + 1] !== "*"
          && !isEscaped(text, end)
        ) break;
        end += 1;
      }
      if (end < text.length) {
        output += `<em>${inlineMarkdown(text.slice(index + 1, end), context)}</em>`;
        index = end + 1;
        continue;
      }
    }
    output += escapeHTML(text[index]);
    index += 1;
  }
  return output;
}

function splitTableRow(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
}

function isTableSeparator(line) {
  const cells = splitTableRow(line);
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell.replaceAll(" ", "")));
}

function slugifyHeading(value) {
  return value.toLowerCase().replace(/[`*_]/g, "").replace(/[^\p{L}\p{N}]+/gu, "-").replace(/^-|-$/g, "");
}

function plainHeadingLabel(value) {
  return String(value || "")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/\\\((.*?)\\\)/g, "$1")
    .replace(/\$([^$]+)\$/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/[*_]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function isBlockStart(lines, index) {
  const line = lines[index] || "";
  const next = lines[index + 1] || "";
  return !line.trim()
    || /^```/.test(line)
    || /^\s*<!--/.test(line)
    || /^#{1,4}\s+/.test(line)
    || /^\s*[-*+]\s+/.test(line)
    || /^\s*\d+\.\s+/.test(line)
    || /^>\s?/.test(line)
    || /^\s*(\$\$|\\\[)/.test(line)
    || /^\s*---+\s*$/.test(line)
    || (line.includes("|") && isTableSeparator(next));
}

function findReaderBlockEnd(lines, start, startPattern, endMarker) {
  let depth = 1;
  for (let cursor = start + 1; cursor < lines.length; cursor += 1) {
    const candidate = lines[cursor].trim();
    if (startPattern.test(candidate)) depth += 1;
    if (candidate === endMarker) {
      depth -= 1;
      if (depth === 0) return cursor;
    }
  }
  return lines.length;
}

function statementFamily(environment) {
  if (["theorem", "proposition", "lemma", "corollary", "claim"].includes(environment)) return "plain";
  if (["definition", "construction"].includes(environment)) return "definition";
  if (environment === "warning") return "warning";
  return "remark";
}

function renderReaderList(lines, index, context, kind, style) {
  const end = findReaderBlockEnd(
    lines,
    index,
    /^<!-- reader-list-start:/,
    "<!-- reader-list-end -->",
  );
  const items = [];
  let current = null;
  let nestedDepth = 0;
  for (let cursor = index + 1; cursor < end; cursor += 1) {
    const sourceLine = lines[cursor];
    const trimmed = sourceLine.trim();
    if (/^<!-- reader-list-start:/.test(trimmed)) {
      nestedDepth += 1;
      if (current) current.lines.push(sourceLine);
      continue;
    }
    if (trimmed === "<!-- reader-list-end -->" && nestedDepth > 0) {
      nestedDepth -= 1;
      if (current) current.lines.push(sourceLine);
      continue;
    }
    const item = nestedDepth === 0
      ? (kind === "enumerate"
          ? sourceLine.match(/^\s*(\d+)\.\s+(.*)$/)
          : sourceLine.match(/^\s*[-*+]\s+(.*)$/))
      : null;
    if (item) {
      if (current) items.push(current);
      current = {
        value: kind === "enumerate" ? Number(item[1]) : null,
        lines: [kind === "enumerate" ? item[2] : item[1]],
      };
    } else if (current) {
      current.lines.push(sourceLine);
    }
  }
  if (current) items.push(current);
  const tag = kind === "enumerate" ? "ol" : "ul";
  const className = `reader-structured-list reader-list-${style}`;
  const start = kind === "enumerate" && items.length ? ` start="${items[0].value}"` : "";
  const body = items.map((item) => {
    const value = kind === "enumerate" ? ` value="${item.value}"` : "";
    return `<li${value}>${renderMarkdown(item.lines.join("\n"), context, true)}</li>`;
  }).join("");
  return { html: `<${tag} class="${escapeHTML(className)}"${start}>${body}</${tag}>`, next: end + 1 };
}

export function renderMarkdown(markdown, context, fragment = false) {
  const lines = String(markdown || "").replaceAll("\r\n", "\n").split("\n");
  const output = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    const listStart = line.trim().match(/^<!-- reader-list-start:(enumerate|itemize):([a-z-]+) -->$/);
    if (listStart) {
      const rendered = renderReaderList(lines, index, context, listStart[1], listStart[2]);
      output.push(rendered.html);
      index = rendered.next;
      continue;
    }
    const statementStart = line.trim().match(/^<!-- reader-statement-start:([a-z*]+) -->$/);
    if (statementStart) {
      const end = findReaderBlockEnd(
        lines,
        index,
        /^<!-- reader-statement-start:/,
        "<!-- reader-statement-end -->",
      );
      const environment = statementStart[1].replace("*", "-star");
      const family = statementFamily(statementStart[1]);
      const body = renderMarkdown(lines.slice(index + 1, end).join("\n"), context, true);
      output.push(`<section class="reader-statement statement-${escapeHTML(environment)} statement-family-${family}">${body}</section>`);
      index = end + 1;
      continue;
    }
    if (line.trim() === "<!-- reader-proof-start -->") {
      const end = findReaderBlockEnd(
        lines,
        index,
        /^<!-- reader-proof-start -->$/,
        "<!-- reader-proof-end -->",
      );
      const proofLines = lines.slice(index + 1, end);
      while (proofLines.length && !proofLines.at(-1).trim()) proofLines.pop();
      if (proofLines.at(-1)?.trim() === "□") proofLines.pop();
      const body = renderMarkdown(proofLines.join("\n"), context, true);
      output.push(`<section class="reader-proof">${body}<div class="reader-proof-end" aria-label="End of proof"><span aria-hidden="true"></span></div></section>`);
      index = end + 1;
      continue;
    }
    if (line.trim().startsWith("<!--")) {
      while (index < lines.length && !lines[index].includes("-->")) index += 1;
      index += index < lines.length ? 1 : 0;
      continue;
    }
    if (!line.trim()) {
      index += 1;
      continue;
    }
    if (line.startsWith("```")) {
      const language = line.slice(3).trim();
      const body = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith("```")) {
        body.push(lines[index]);
        index += 1;
      }
      index += index < lines.length ? 1 : 0;
      output.push(`<pre data-language="${escapeHTML(language)}"><code>${escapeHTML(body.join("\n"))}</code></pre>`);
      continue;
    }
    if (/^\s*(\$\$|\\\[)/.test(line)) {
      const math = parseDisplayMath(lines, index);
      output.push(math.html);
      index = math.next;
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      const level = heading[1].length;
      const title = heading[2].trim();
      output.push(`<h${level} id="${escapeHTML(slugifyHeading(title))}" data-outline-label="${escapeHTML(plainHeadingLabel(title))}">${inlineMarkdown(title, context)}</h${level}>`);
      index += 1;
      continue;
    }
    if (line.includes("|") && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
      const header = splitTableRow(line);
      const rows = [];
      index += 2;
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        rows.push(splitTableRow(lines[index]));
        index += 1;
      }
      output.push(`<table><thead><tr>${header.map((cell) => `<th>${inlineMarkdown(cell, context)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${inlineMarkdown(cell, context)}</td>`).join("")}</tr>`).join("")}</tbody></table>`);
      continue;
    }
    if (/^\s*[-*+]\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^\s*[-*+]\s+/.test(lines[index])) {
        let item = lines[index].replace(/^\s*[-*+]\s+/, "");
        const checkbox = item.match(/^\[([ xX])\]\s+(.*)$/);
        if (checkbox) {
          item = `<input type="checkbox" disabled ${checkbox[1].toLowerCase() === "x" ? "checked" : ""}> ${inlineMarkdown(checkbox[2], context)}`;
        } else {
          item = inlineMarkdown(item, context);
        }
        items.push(`<li>${item}</li>`);
        index += 1;
      }
      output.push(`<ul>${items.join("")}</ul>`);
      continue;
    }
    if (/^\s*\d+\.\s+/.test(line)) {
      const items = [];
      const start = Number(line.match(/^\s*(\d+)\./)?.[1] || 1);
      while (index < lines.length && /^\s*\d+\.\s+/.test(lines[index])) {
        items.push(`<li>${inlineMarkdown(lines[index].replace(/^\s*\d+\.\s+/, ""), context)}</li>`);
        index += 1;
      }
      output.push(`<ol start="${start}">${items.join("")}</ol>`);
      continue;
    }
    if (/^>\s?/.test(line)) {
      const body = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) {
        body.push(lines[index].replace(/^>\s?/, ""));
        index += 1;
      }
      output.push(`<blockquote>${renderMarkdown(body.join("\n"), context, true)}</blockquote>`);
      continue;
    }
    if (/^\s*---+\s*$/.test(line)) {
      output.push("<hr>");
      index += 1;
      continue;
    }

    const paragraph = [line.trim()];
    index += 1;
    while (index < lines.length && !isBlockStart(lines, index)) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    output.push(`<p>${inlineMarkdown(paragraph.join(" "), context)}</p>`);
  }
  return fragment ? output.join("") : `<div class="markdown-body">${output.join("")}</div>`;
}

export function renderSource(content, locator = null) {
  return `<pre class="source-code">${String(content).replaceAll("\r\n", "\n").split("\n").map((line, index) => {
    const lineNumber = index + 1;
    const highlighted = locator && lineNumber >= locator.start && lineNumber <= locator.end;
    return `<span id="source-L${lineNumber}" class="source-line${highlighted ? " is-target" : ""}" data-line="${lineNumber}">${escapeHTML(line) || " "}</span>`;
  }).join("")}</pre>`;
}
