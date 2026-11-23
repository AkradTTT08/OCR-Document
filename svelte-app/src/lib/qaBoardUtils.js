/**
 * Shared helpers for QA Board Card (Kanban & QA Execution Table)
 */

export function isHeaderCard(title, colTitles = []) {
  const t = (title || '').trim().toLowerCase();
  if (!t) return true;

  const defaultHeaders = [
    'deploy', 'review', 'to do', 'todo', 'doing', 'in progress', 'testing',
    'testing (agent)', 'template & plan', 'done', 'backlog', 'done back log',
    'done (current sprint card)', 'done (back log card)'
  ];
  if (defaultHeaders.includes(t)) return true;

  for (const c of colTitles) {
    const cLow = (c || '').trim().toLowerCase();
    if (cLow && (t === cLow || t.startsWith(cLow + ' (') || t.startsWith(cLow + '('))) {
      return true;
    }
  }

  const headerKeywords = [
    'sprint card', 'back log card', 'backlog card', 'header card',
    'placeholder card', 'section header', 'separator'
  ];
  return headerKeywords.some(kw => t.includes(kw));
}

export function getCleanLabels(labels) {
  if (!labels || !Array.isArray(labels)) return [];
  const seen = new Set();
  const result = [];
  for (const l of labels) {
    const rawName = typeof l === 'string' ? l : (l.name || '');
    const name = rawName.replace(/[*_`~#]/g, '').trim();
    const lower = name.toLowerCase();
    if (name && !seen.has(lower)) {
      seen.add(lower);
      const color = (typeof l === 'object' && l?.color) ? l.color : '#6366f1';
      result.push({
        ...(typeof l === 'object' ? l : {}),
        name,
        color,
        textColor: getLabelTextColor(color)
      });
    }
  }
  return result;
}

/**
 * Compute accessible text color (#0a0b12 or #f8fafc) for arbitrary label background colors
 */
export function getLabelTextColor(colorStr) {
  if (!colorStr || typeof colorStr !== 'string') return '#f8fafc';
  const hex = colorStr.trim().replace(/^#/, '');
  let r = 99, g = 102, b = 241;
  if (/^[0-9a-fA-F]{3}$/.test(hex)) {
    r = parseInt(hex[0] + hex[0], 16);
    g = parseInt(hex[1] + hex[1], 16);
    b = parseInt(hex[2] + hex[2], 16);
  } else if (/^[0-9a-fA-F]{6}$/.test(hex)) {
    r = parseInt(hex.slice(0, 2), 16);
    g = parseInt(hex.slice(2, 4), 16);
    b = parseInt(hex.slice(4, 6), 16);
  } else {
    return '#f8fafc';
  }
  const toLinear = (c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  const lum = 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
  return lum > 0.34 ? '#0a0b12' : '#f8fafc';
}

/**
 * Determine accurate test status for a card ('testing' | 'failed' | 'passed' | 'untested')
 */
export function getCardVerdict(card) {
  if (!card) return 'untested';
  if (card.isTesting) return 'testing';
  const rawVerdict = String(card.verdict || '').toUpperCase();
  const rawResult = typeof card.test_result === 'string'
    ? card.test_result.toUpperCase()
    : (card.test_result ? JSON.stringify(card.test_result).toUpperCase() : '');

  if (!rawVerdict && !rawResult) return 'untested';
  if (rawVerdict.includes('FAIL') || rawVerdict.includes('REJECT') || rawResult.includes('FAILED')) {
    return 'failed';
  }
  if (rawVerdict.includes('PASS') || rawResult.includes('PASSED')) {
    return 'passed';
  }
  return 'passed';
}

export function getPriorityMeta(card) {
  const rawPrio = String(card?.priority || 'Medium').trim();
  const low = rawPrio.toLowerCase();
  if (low === 'high' || low === 'critical') {
    return { level: 'high', label: 'High Priority' };
  }
  if (low === 'low') {
    return { level: 'low', label: 'Low Priority' };
  }
  return { level: 'medium', label: card?.type && card.type !== 'Main Card' ? card.type : 'Medium' };
}

export function resolveMemberName(mId, membersList = []) {
  if (!mId) return '';
  const found = (membersList || []).find(
    m => m.id === mId || m.username === mId || m.name === mId
  );
  if (found) {
    return found.name || (found.username ? `@${found.username}` : String(mId));
  }
  return String(mId);
}

export function parseCommentSegments(rawText, pId) {
  if (!rawText) return [];

  const isVideoExt = (url) => {
    const u = url.toLowerCase().split('?')[0];
    return u.endsWith('.mp4') || u.endsWith('.webm') || u.endsWith('.mov') || u.endsWith('.mkv') || u.endsWith('.avi');
  };

  const isImageExt = (url) => {
    const u = url.toLowerCase().split('?')[0];
    return u.endsWith('.png') || u.endsWith('.jpg') || u.endsWith('.jpeg') || u.endsWith('.gif') || u.endsWith('.webp') || u.endsWith('.svg') || u.endsWith('.bmp');
  };

  const processUrl = (url) => {
    if (url.includes('trello.com/') || url.includes('trello-attachments.s3.amazonaws.com/')) {
      return `/api/projects/${pId}/attachment-proxy?url=${encodeURIComponent(url)}`;
    }
    return url;
  };

  const masterRegex = /!\[([^\]]*)\]\((https?:\/\/[^\s\)]+)\)|\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)|(https?:\/\/[^\s\)]+)/g;

  const segments = [];
  let lastIdx = 0;
  let match;

  while ((match = masterRegex.exec(rawText)) !== null) {
    if (match.index > lastIdx) {
      const textPart = rawText.slice(lastIdx, match.index);
      if (textPart) {
        segments.push({ type: 'text', content: textPart });
      }
    }

    if (match[2]) {
      const alt = match[1] || 'Attached image';
      const rawUrl = match[2];
      const finalUrl = processUrl(rawUrl);
      if (isVideoExt(rawUrl)) {
        segments.push({ type: 'video', alt: alt || 'Attached video', url: finalUrl, originalUrl: rawUrl });
      } else {
        segments.push({ type: 'image', alt, url: finalUrl, originalUrl: rawUrl });
      }
    } else if (match[4]) {
      const linkText = match[3];
      const rawUrl = match[4];
      const finalUrl = processUrl(rawUrl);
      if (isVideoExt(rawUrl)) {
        segments.push({ type: 'video', alt: linkText || 'Attached video', url: finalUrl, originalUrl: rawUrl });
      } else if (isImageExt(rawUrl)) {
        segments.push({ type: 'image', alt: linkText || 'Attached image', url: finalUrl, originalUrl: rawUrl });
      } else {
        segments.push({ type: 'link', text: linkText, url: finalUrl, originalUrl: rawUrl });
      }
    } else if (match[5]) {
      const rawUrl = match[5];
      const finalUrl = processUrl(rawUrl);
      if (isVideoExt(rawUrl)) {
        segments.push({ type: 'video', alt: 'Attached video', url: finalUrl, originalUrl: rawUrl });
      } else if (isImageExt(rawUrl) || rawUrl.includes('trello-attachments.s3.amazonaws.com') || rawUrl.includes('trello.com/1/cards/')) {
        segments.push({ type: 'image', alt: 'Attached image', url: finalUrl, originalUrl: rawUrl });
      } else {
        segments.push({ type: 'link', text: rawUrl, url: finalUrl, originalUrl: rawUrl });
      }
    }

    lastIdx = masterRegex.lastIndex;
  }

  if (lastIdx < rawText.length) {
    const remaining = rawText.slice(lastIdx);
    if (remaining) {
      segments.push({ type: 'text', content: remaining });
    }
  }

  return segments.length > 0 ? segments : [{ type: 'text', content: rawText }];
}

