// Pure helper: normalises AI-generated Mermaid code so it renders reliably.
// Extracted from QAAnalysisDiagram.svelte (no component state used).

export function sanitizeMermaidCode(raw) {
  if (!raw) return "";
  let text = raw.trim();

  // 1. Remove markdown code fences if present (```mermaid ... ```)
  text = text.replace(/^```(?:mermaid)?\s*/i, '').replace(/\s*```$/, '').trim();

  // 2. If it's a sequence diagram, preserve sequence syntax
  if (/^\s*sequenceDiagram/i.test(text)) {
    return text;
  }

  // Ensure header starts with flowchart
  if (!/^\s*(flowchart|graph)\b/i.test(text)) {
    text = `flowchart TD\n${text}`;
  }

  const lines = text.split(/\r?\n/);
  const resultLines = [];

  // Helper: clean and wrap text safely
  const cleanLabel = (s) => {
    if (!s) return "";
    let t = String(s).trim();
    if ((t.startsWith('"') && t.endsWith('"')) || (t.startsWith("'") && t.endsWith("'"))) {
      t = t.slice(1, -1).trim();
    }
    return t.replace(/"/g, "'");
  };

  for (let line of lines) {
    let l = line.trimEnd();

    // Skip empty lines
    if (!l.trim()) {
      resultLines.push("");
      continue;
    }

    // Skip directives and comments
    if (/^\s*(%%|classDef|class|click|style|linkStyle|accTitle|accDescr)\b/i.test(l)) {
      resultLines.push(l);
      continue;
    }

    const indent = l.match(/^\s*/)[0];

    // A. Fix actor declaration in flowchart: `actor Customer as "ผู้ใช้งาน"` or `actor Customer`
    if (/^\s*actor\b/i.test(l)) {
      const actorMatch = l.match(/^\s*actor\s+([A-Za-z0-9_]+)(?:\s+(?:as\s+)?(.*))?$/i);
      if (actorMatch) {
        const id = actorMatch[1];
        const label = cleanLabel(actorMatch[2]) || id;
        resultLines.push(`${indent}${id}["👤 ${label}"]`);
        continue;
      }
    }

    // B. Fix Subgraph: `subgraph ID [Title]` or `subgraph ID ["Title"]` or `subgraph [Title]`
    const subgraphMatch = l.match(/^(\s*subgraph\s+[A-Za-z0-9_]+)\s*\[\s*([^\]]+?)\s*\]\s*$/i);
    if (subgraphMatch) {
      const title = cleanLabel(subgraphMatch[2]);
      resultLines.push(`${subgraphMatch[1]} ["${title}"]`);
      continue;
    }

    // C. Fix PlantUML / dotted arrows with colons:
    l = l.replace(/([A-Za-z0-9_]+)\s*<\.\.\s*([A-Za-z0-9_]+)\s*:\s*<?<?([^>\r\n]+)>?>?/g, (m, left, right, label) => {
      return `${right} -.->|"${cleanLabel(label)}"| ${left}`;
    });
    l = l.replace(/([A-Za-z0-9_]+)\s*\.\.>\s*([A-Za-z0-9_]+)\s*:\s*<?<?([^>\r\n]+)>?>?/g, (m, left, right, label) => {
      return `${left} -.->|"${cleanLabel(label)}"| ${right}`;
    });
    l = l.replace(/([A-Za-z0-9_]+)\s*<\.\.\s*([A-Za-z0-9_]+)/g, '$2 -.-> $1');
    l = l.replace(/([A-Za-z0-9_]+)\s*\.\.>\s*([A-Za-z0-9_]+)/g, '$1 -.-> $2');

    // D. Fix arrow with colon label: `A --> B : text`
    l = l.replace(/([A-Za-z0-9_]+)\s*(-->|-\.->|==>)\s*([A-Za-z0-9_]+)\s*:\s*([^\r\n]+)/g, (m, left, arrow, right, label) => {
      return `${left} ${arrow}|"${cleanLabel(label)}"| ${right}`;
    });

    // E. Fix inline arrow labels:
    // `-- (label) -->` or `-- label -->`
    l = l.replace(/--\s*(?:\(([^()\r\n]+)\)|([^->\r\n|]+?))\s*-->/g, (m, p1, p2) => {
      return `-->|"${cleanLabel(p1 || p2)}"|`;
    });
    l = l.replace(/--\s*(?:\(([^()\r\n]+)\)|([^->\r\n|]+?))\s*--\s*>/g, (m, p1, p2) => {
      return `-->|"${cleanLabel(p1 || p2)}"|`;
    });
    // `== (label) ==>` or `== label ==>`
    l = l.replace(/==\s*(?:\(([^()\r\n]+)\)|([^=>\r\n|]+?))\s*==>/g, (m, p1, p2) => {
      return `==>|"${cleanLabel(p1 || p2)}"|`;
    });
    // `-. (label) .->` or `-. label .->`
    l = l.replace(/-\.\s*(?:\(([^()\r\n]+)\)|([^->\r\n|]+?))\s*\.->/g, (m, p1, p2) => {
      return `-.->|"${cleanLabel(p1 || p2)}"|`;
    });

    // F. Rename reserved node ID `End` or `end` to `EndNode` if not a standalone `end` line
    if (!/^\s*end\s*$/i.test(l)) {
      l = l.replace(/\bEnd\s*\(\[\s*(.*?)\s*\]\)/g, 'EndNode(["$1"])');
      l = l.replace(/\bEnd\s*\[\s*(.*?)\s*\]/g, 'EndNode["$1"]');
      l = l.replace(/\bEnd\s*\(\s*(.*?)\s*\)/g, 'EndNode("$1")');
      l = l.replace(/(-->|-\.->|==>)\s*End\b/g, '$1 EndNode');
      l = l.replace(/\bEnd\s*(-->|-\.->|==>)/g, 'EndNode $1');
    }

    // Step G: TOKENIZE & SAFELY QUOTE ALL NODES ON THIS LINE
    const nodeTokens = [];
    const addToken = (id, formattedNode) => {
      const idx = nodeTokens.length;
      nodeTokens.push({ id, formattedNode });
      return `__NODE_TOKEN_${idx}__`;
    };

    // 1. Stadium / Pill: `ID([ ... ])`
    l = l.replace(/([A-Za-z0-9_]+)\s*\(\[\s*([\s\S]*?)\s*\]\)/g, (m, id, inner) => {
      return addToken(id, `${id}(["${cleanLabel(inner)}"])`);
    });

    // 2. Circle: `ID(( ... ))`
    l = l.replace(/([A-Za-z0-9_]+)\s*\(\(\s*([\s\S]*?)\s*\)\)/g, (m, id, inner) => {
      return addToken(id, `${id}(("${cleanLabel(inner)}"))`);
    });

    // 3. Database Cylinder: `ID[( ... )]` or `ID[(" ... ")]`
    l = l.replace(/([A-Za-z0-9_]+)\s*\[\(\s*([\s\S]*?)\s*\)\]/g, (m, id, inner) => {
      return addToken(id, `${id}[("${cleanLabel(inner)}")]`);
    });

    // 4. Hexagon: `ID{{ ... }}`
    l = l.replace(/([A-Za-z0-9_]+)\s*\{\{\s*([\s\S]*?)\s*\}\}/g, (m, id, inner) => {
      return addToken(id, `${id}{{"${cleanLabel(inner)}"}}`);
    });

    // 5. Rhombus / Decision: `ID{ ... }`
    l = l.replace(/([A-Za-z0-9_]+)\s*\{\s*([\s\S]*?)\s*\}/g, (m, id, inner) => {
      return addToken(id, `${id}{"${cleanLabel(inner)}"}`);
    });

    // 6. Standard Box: `ID[ ... ]` (ignore subgraph lines)
    if (!/^\s*subgraph\b/i.test(l)) {
      l = l.replace(/([A-Za-z0-9_]+)\s*\[\s*([\s\S]*?)\s*\]/g, (m, id, inner) => {
        return addToken(id, `${id}["${cleanLabel(inner)}"]`);
      });
    }

    // 7. Rounded Box: `ID( ... )`
    l = l.replace(/([A-Za-z0-9_]+)\s*\(\s*([\s\S]*?)\s*\)/g, (m, id, inner) => {
      return addToken(id, `${id}("${cleanLabel(inner)}")`);
    });

    // H. Clean pipe labels |...|
    l = l.replace(/\|([^|]+)\|/g, (m, rawPipe) => {
      return `|"${cleanLabel(rawPipe)}"|`;
    });

    // I. Handle chained edges like `A -->|label| __NODE_TOKEN_0__ --> B`
    // Split into two lines: `A -->|label| __NODE_TOKEN_0__` and `TARGET_ID --> B`
    const chainMatch = l.match(/^(\s*)(.*?(?:-->|-\.->|==>).*?\s+)(__NODE_TOKEN_(\d+)__)\s*(-->|-\.->|==>)\s*(.+)$/);
    if (chainMatch) {
      const lineIndent = chainMatch[1];
      const tokenIdx = parseInt(chainMatch[4], 10);
      const middleNodeId = nodeTokens[tokenIdx] ? nodeTokens[tokenIdx].id : chainMatch[3];
      const firstPart = `${lineIndent}${chainMatch[2]}${chainMatch[3]}`;
      const secondPart = `${lineIndent}${middleNodeId} ${chainMatch[5]} ${chainMatch[6].trim()}`;

      // Restore tokens for firstPart
      let resFirst = firstPart.replace(/__NODE_TOKEN_(\d+)__/g, (tm, tIdx) => {
        return nodeTokens[parseInt(tIdx, 10)]?.formattedNode || tm;
      });
      // Restore tokens for secondPart
      let resSecond = secondPart.replace(/__NODE_TOKEN_(\d+)__/g, (tm, tIdx) => {
        return nodeTokens[parseInt(tIdx, 10)]?.formattedNode || tm;
      });

      resultLines.push(resFirst);
      resultLines.push(resSecond);
      continue;
    }

    // J. Restore all node tokens
    l = l.replace(/__NODE_TOKEN_(\d+)__/g, (tm, tIdx) => {
      return nodeTokens[parseInt(tIdx, 10)]?.formattedNode || tm;
    });

    resultLines.push(l);
  }

  // Auto-close any unclosed subgraphs
  let subgraphCount = 0;
  let endCount = 0;
  for (const line of resultLines) {
    if (/^\s*subgraph\b/i.test(line)) subgraphCount++;
    if (/^\s*end\s*$/i.test(line.trim())) endCount++;
  }
  while (subgraphCount > endCount) {
    resultLines.push('  end');
    endCount++;
  }

  return resultLines.join('\n');
}

// Design-token mirror of DESIGN.md ("Spectrum Command Deck") for Mermaid, which needs literal colours.
export const mermaidThemeVariables = {
  darkMode: true,
  background: '#0f111a',
  primaryColor: '#6366f1',
  primaryTextColor: '#f8fafc',
  primaryBorderColor: '#818cf8',
  lineColor: '#94a3b8',
  secondaryColor: '#a855f7',
  tertiaryColor: '#161926'
};
