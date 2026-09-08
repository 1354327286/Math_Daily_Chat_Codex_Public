#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const katex = require(path.resolve(__dirname, "../dashboard/vendor/katex/katex.js")).katex;

function isEscaped(text, index) {
  let backslashes = 0;
  for (let cursor = index - 1; cursor >= 0 && text[cursor] === "\\"; cursor -= 1) {
    backslashes += 1;
  }
  return backslashes % 2 === 1;
}

function lineNumber(text, index) {
  return text.slice(0, index).split("\n").length;
}

function excerpt(value) {
  return value.replace(/\s+/g, " ").trim().slice(0, 180);
}

function auditMath(tex, displayMode, source, offset, errors) {
  try {
    katex.renderToString(tex, {
      displayMode,
      throwOnError: true,
      strict: "ignore",
      trust: false,
      maxSize: 30,
      maxExpand: 1000,
      output: "htmlAndMathml",
    });
  } catch (error) {
    errors.push({
      line: lineNumber(source, offset),
      mode: displayMode ? "display" : "inline",
      message: error.message,
      excerpt: excerpt(tex),
    });
  }
}

function main() {
  const readerPath = process.argv[2];
  if (!readerPath) {
    process.stderr.write("usage: node check_tex_reader_math.cjs READER.md\n");
    return 2;
  }
  const source = fs.readFileSync(readerPath, "utf8");
  const errors = [];
  let displayCount = 0;
  const displayPattern = /\$\$([\s\S]*?)\$\$|\\\[([\s\S]*?)\\\]/g;
  const inlineSource = source.replace(
    displayPattern,
    (whole, dollars, brackets, offset) => {
      auditMath(dollars ?? brackets ?? "", true, source, offset, errors);
      displayCount += 1;
      return whole.replace(/[^\n]/g, " ");
    },
  );

  let inlineCount = 0;
  for (let index = 0; index < inlineSource.length; index += 1) {
    if (inlineSource[index] !== "$" || inlineSource[index + 1] === "$" || isEscaped(inlineSource, index)) {
      continue;
    }
    let end = index + 1;
    while (end < inlineSource.length) {
      if (inlineSource[end] === "$" && inlineSource[end + 1] !== "$" && !isEscaped(inlineSource, end)) {
        break;
      }
      if (inlineSource[end] === "\n") {
        end = inlineSource.length;
        break;
      }
      end += 1;
    }
    if (end >= inlineSource.length) continue;
    auditMath(inlineSource.slice(index + 1, end), false, source, index, errors);
    inlineCount += 1;
    index = end;
  }

  if (errors.length) {
    for (const error of errors) {
      process.stderr.write(
        readerPath + ":" + error.line + ": " + error.mode + " math: "
        + error.message + "\n  " + error.excerpt + "\n",
      );
    }
    return 1;
  }
  process.stdout.write(
    "KaTeX math audit passed: " + displayCount + " display, "
    + inlineCount + " inline, 0 errors\n",
  );
  return 0;
}

process.exitCode = main();
