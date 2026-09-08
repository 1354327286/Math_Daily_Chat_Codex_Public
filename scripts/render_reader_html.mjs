#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

import { renderMarkdown } from "../dashboard/reader-renderer.mjs";

function usage() {
  process.stderr.write("usage: node render_reader_html.mjs READER_MD LINK_MAP_JSON OUTPUT_JSON\n");
  return 2;
}

function uniqueHeadingIds(html) {
  const used = new Set();
  const headings = [];
  let index = 0;
  const rendered = html.replace(
    /<h([1-4]) id="([^"]*)" data-outline-label="([^"]*)">/g,
    (_whole, rawLevel, rawId, label) => {
      index += 1;
      const base = rawId || `reader-heading-${index}`;
      let identifier = base;
      let suffix = 2;
      while (used.has(identifier)) {
        identifier = `${base}-${suffix}`;
        suffix += 1;
      }
      used.add(identifier);
      headings.push({ level: Number(rawLevel), id: identifier, label });
      return `<h${rawLevel} id="${identifier}" data-outline-label="${label}">`;
    },
  );
  return { html: rendered, headings };
}

function main() {
  const [readerArgument, mapArgument, outputArgument] = process.argv.slice(2);
  if (!readerArgument || !mapArgument || !outputArgument) return usage();

  const readerPath = path.resolve(readerArgument);
  const mapPath = path.resolve(mapArgument);
  const outputPath = path.resolve(outputArgument);
  const markdown = fs.readFileSync(readerPath, "utf8");
  const linkMap = JSON.parse(fs.readFileSync(mapPath, "utf8"));
  const context = {
    offline: true,
    showPdfPageHints: true,
    resolveLocalLink: (target) => Object.hasOwn(linkMap, target) ? linkMap[target] : null,
  };
  const rendered = uniqueHeadingIds(renderMarkdown(markdown, context));
  const result = {
    html: rendered.html,
    headings: rendered.headings,
    math_errors: (rendered.html.match(/data-math-error="true"/g) || []).length,
  };
  fs.writeFileSync(outputPath, `${JSON.stringify(result)}\n`, "utf8");
  return 0;
}

process.exitCode = main();
