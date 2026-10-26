/* MINE QUEST: standalone rules engine (no DOM, no dependencies). */
(function (root) {
  'use strict';
  function neighbors(index, rows, cols) {
    const r = Math.floor(index / cols), c = index % cols, result = [];
    for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) {
      if (dr === 0 && dc === 0) continue;
      const nr = r + dr, nc = c + dc;
      if (nr >= 0 && nr < rows && nc >= 0 && nc < cols) result.push(nr * cols + nc);
    }
    return result;
  }
  function empty(rows, cols) {
    if (!Number.isInteger(rows) || !Number.isInteger(cols) || rows < 2 || cols < 2 || rows * cols > 2000) throw Error('Invalid board size');
    return Array.from({length: rows * cols}, (_, index) => ({index, mine: false, number: 0, open: false, flag: false, exploded: false}));
  }
  function generate(rows, cols, count, firstSafeIndex, random = Math.random) {
    if (!Number.isInteger(count) || count < 0 || count >= rows * cols) throw Error('Invalid mine count');
    if (!Number.isInteger(firstSafeIndex) || firstSafeIndex < 0 || firstSafeIndex >= rows * cols) throw Error('Invalid first cell');
    const cells = empty(rows, cols);
    const protectedSet = new Set([firstSafeIndex, ...neighbors(firstSafeIndex, rows, cols)]);
    // Under unusually dense custom boards, always preserve the clicked cell.
    if (rows * cols - protectedSet.size < count) { protectedSet.clear(); protectedSet.add(firstSafeIndex); }
    const options = cells.map(c => c.index).filter(i => !protectedSet.has(i));
    for (let k = 0; k < count; k++) {
      const j = k + Math.floor(Math.min(.999999999999, Math.max(0, random())) * (options.length - k));
      [options[k], options[j]] = [options[j], options[k]];
      cells[options[k]].mine = true;
    }
    for (const c of cells) if (!c.mine) c.number = neighbors(c.index, rows, cols).filter(j => cells[j].mine).length;
    return cells;
  }
  function reveal(cells, rows, cols, index) {
    const changed = [], detonated = [];
    if (!cells[index] || cells[index].open || cells[index].flag) return {changed, detonated};
    const seen = new Set(), queue = [index];
    for (let ptr = 0; ptr < queue.length; ptr++) {
      const i = queue[ptr], cell = cells[i];
      if (seen.has(i) || cell.open || cell.flag) continue;
      seen.add(i);
      cell.open = true; changed.push(i);
      if (cell.mine) { cell.exploded = true; detonated.push(i); continue; }
      if (cell.number === 0) {
        for (const n of neighbors(i, rows, cols)) if (!seen.has(n) && !cells[n].open && !cells[n].flag && !cells[n].mine) queue.push(n);
      }
    }
    return {changed, detonated};
  }
  function chord(cells, rows, cols, index) {
    const cell = cells[index];
    if (!cell || !cell.open || cell.mine || cell.number === 0) return {changed: [], detonated: []};
    const adjacent = neighbors(index, rows, cols);
    if (adjacent.filter(i => cells[i].flag).length !== cell.number) return {changed: [], detonated: []};
    const changed = [], detonated = [];
    for (const i of adjacent) {
      if (!cells[i].open && !cells[i].flag) {
        const next = reveal(cells, rows, cols, i);
        changed.push(...next.changed); detonated.push(...next.detonated);
      }
    }
    return {changed, detonated};
  }
  function flag(cells, index) {
    const cell = cells[index];
    if (!cell || cell.open) return null;
    cell.flag = !cell.flag;
    return cell.flag;
  }
  function count(cells) {
    const safe = cells.filter(c => !c.mine);
    return {openedSafe: safe.filter(c => c.open).length, totalSafe: safe.length,
      flagged: cells.filter(c => c.flag).length, correctFlags: cells.filter(c => c.flag && c.mine).length,
      mines: cells.filter(c => c.mine).length,
      cleared: safe.every(c => c.open)};
  }
  root.MineEngine = Object.freeze({neighbors, empty, generate, reveal, chord, flag, count});
  if (typeof module !== 'undefined' && module.exports) module.exports = root.MineEngine;
})(typeof globalThis !== 'undefined' ? globalThis : this);
