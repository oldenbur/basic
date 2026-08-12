var fs = require('fs');

const inputRe = /^(\w) (\d+)$/

const s = (obj) => JSON.stringify(obj)
const sa = (arr) => arr.map(o => JSON.stringify(o))
const ss = (set) => Array.from(set.values())

const toInc = move => 
  move.d === "U" ?       [-1, 0]
  : move.d === "D" ?     [1, 0]
  : move.d === "L" ?     [0, -1]
  : /* move.d === "R" */ [0, 1]

const moveRope = (move, rope, path) => {
  if (move.n <= 0) {
    return rope
  }

  const inc = toInc(move)
  let hNew = {r: rope[0].r + inc[0], c: rope[0].c + inc[1]}
  //console.log(`ropeH - move:${s(move)} hNew:${s(hNew)}`)
  ropeNew = [hNew, 
    ...rope.slice(1).map((r, i) => {
      //console.log(`sliceMap - r:${s(r)} i:${i} rope:${sa(rope)}`)
      let tNew = doMove(rope[i], hNew, r)
      //console.log(`rope - i:${i+1} tNew:${s(tNew)}`)
      if (i === rope.length-2) {
        //console.log(`path:${sa(path)}`)
        path.push(tNew)
      }
      hNew = tNew
      return tNew
    })
  ] 
  //drawRope(ropeNew)
  return moveRope({d:move.d, n:move.n-1}, ropeNew, path)    
}

const doMove = (h, hNew, t) => {
  //console.log(`doMove - h:${s(h)} hNew:${s(hNew)} t:${s(t)}`)
  const inc = [hNew.r - h.r, hNew.c - h.c]
  const rDiff = Math.abs(h.r - t.r)
  const cDiff = Math.abs(h.c - t.c)
  const rnDiff = Math.abs(hNew.r - t.r)
  const cnDiff = Math.abs(hNew.c - t.c)
  const tNew =
    (rnDiff === 0 && cnDiff > 1) ?
      {r: t.r, c: t.c + inc[1]} // follow vertically
    : (cnDiff === 0 && rnDiff > 1) ?
      {r: t.r + inc[0], c: t.c} // follow horizontally
    : (cnDiff > 1 || rnDiff > 1) ?  
      {r: rnDiff > 1 ? t.r + inc[0] : hNew.r,
        c: cnDiff > 1 ? t.c + inc[1] : hNew.c} // follow diagonally
    : t // no move

  return tNew
}

const testDoMove = () => {
  assertEquals(doMove({r:0, c:1}, {r:0, c:2}, {r:0, c:0}), {r:0, c:1})
  assertEquals(doMove({r:1, c:1}, {r:2, c:2}, {r:0, c:0}), {r:1, c:1})
  assertEquals(doMove({r:1, c:1}, {r:2, c:1}, {r:0, c:0}), {r:1, c:1})
  assertEquals(doMove({r:1, c:1}, {r:2, c:0}, {r:0, c:0}), {r:1, c:0})
  assertEquals(doMove({r:0, c:1}, {r:1, c:0}, {r:0, c:0}), {r:0, c:0})
  assertEquals(doMove({r:0, c:1}, {r:1, c:2}, {r:0, c:0}), {r:1, c:1})
  assertEquals(doMove({r:1, c:0}, {r:2, c:1}, {r:0, c:0}), {r:1, c:1})
}

const doMoveOrig = (h, hNew, t) => {
  //console.log(`doMove - h:${s(h)} hNew:${s(hNew)} t:${s(t)}`)
  const inc = [hNew.r - h.r, hNew.c - h.c]
  const rDiff = Math.abs(h.r - t.r)
  const cDiff = Math.abs(h.c - t.c)
  const rnDiff = Math.abs(hNew.r - t.r)
  const cnDiff = Math.abs(hNew.c - t.c)
  const tNew =
    (rDiff === 0 && cnDiff > 1) || (cDiff === 0 && rnDiff > 1) ?
      {r: t.r + inc[0], c: t.c + inc[1]} // follow in same row/column
    : (cnDiff > 1 || rnDiff > 1) ?  h // follow diagonally
    : t // no move

  return tNew
}

const assertEquals = (act, exp) => {
  if (s(act) !== s(exp)) {
    console.log(`Expected '${s(exp)}' is NOT equal to actual '${s(act)}'`)
  } else {
    console.log(`Expected '${s(exp)}' is equal to actual '${s(act)}'`)
  }
}

const doMove2 = (move, h, t, path) => {
  if (move.n <= 0) {
    return {h, t}
  }

  const inc = toInc(move)
  const hNew = {r: h.r + inc[0], c: h.c + inc[1]}
  const tNew = doMove(h, hNew, t)
  path.push(tNew)
  console.log(`move:${s(move)} h:${s(h)} t:${s(t)} hNew: ${s(hNew)} tNew:${s(tNew)} path:${sa(path)}`)
  return doMove2({d:move.d, n:move.n-1}, hNew, tNew, path)    
}

const bounds = (rope) => {
  let top = Number.MIN_SAFE_INTEGER
  let bot = Number.MAX_SAFE_INTEGER
  let lef = Number.MAX_SAFE_INTEGER
  let rig = Number.MIN_SAFE_INTEGER

  rope.forEach((r) => {
    if (r.r > top) top = r.r
    if (r.r < bot) bot = r.r
    if (r.c < lef) lef = r.c
    if (r.c > rig) rig = r.c
  })
  return {ll:{r:bot, c:lef}, ur:{r:top, c:rig}}
}

const drawRope = (rope) => {
  b = bounds(rope)
  box = []
  for (let r=b.ll.r; r <= b.ur.r; r++) {
    row = []
    for(let c=b.ll.c; c <= b.ur.c; c++) { row.push('.') }
    box.push(row)
  }
  rope.forEach((r,i) => { box[r.r - b.ll.r][r.c - b.ll.c] = i})
  box.forEach(r => console.log(`${r.join('')}`))
}

const part2 = (moves) => {

  //const moves = [{d:"U", n:2}]
  const path2 = []
  let rope = []
  for (let i=0; i < 10; i++) { rope.push({r:0, c:0}) }
  moves.forEach((move, i) => {
    rope = moveRope(move, rope, path2)
    //drawRope(rope)
  })
  const cover2 = new Set(path2.map(p => JSON.stringify(p)))
  console.log(`answer2:${cover2.size}`)
}

fs.readFile('2022d9.data', 'utf8', (err, data) => {
  if (err) throw err;

  const moves = data.split('\n').filter(line => line !== '')
    .map(line => {
      [u, d, n] = line.match(inputRe)
      return {d, n:Number(n)}
    })

//  const path1 = []
//  let pos = {h:{r:0,c:0},t:{r:0,c:0}}
//  moves.forEach((move, i) => { pos = doMove2(move, pos.h, pos.t, path1) })
//  const cover1 = new Set(path1.map(p => JSON.stringify(p)))
//  console.log(`answer1:${cover1.size}`)

  //const moves = [{d:"U", n:2}]
  part2(moves)
  //testDoMove()
});


