// https://adventofcode.com/2022/day/3
//

var fs = require('fs');
const matchRe = /^move/
const labelRe = /^ 1 /
const blockRe = /^\[([A-Za-z])\] ?$/
const moveRe = /^move ([0-9]+) from ([0-9]+) to ([0-9]+)$/

fs.readFile('2022d5.data', 'utf8', (err, data) => {
  if (err) throw err;

  const lines = data.split('\n').filter(line => line !== '')
  const labels = lines.filter(line => line.match(labelRe))[0]
  const slots = labels.split(/ +/).length - 2
  const moves = lines.filter(line => line.match(matchRe))
  const blocks = 
    lines.filter(line => !line.match(matchRe) && !line.match(labelRe))
      .reverse()

  console.log(`labels: ${labels} - ${slots}\nblocks:\n${blocks}\nmoves:\n${moves}`)

  const stacks=[]
  for (let s=0; s < slots; s++) {
    stacks.push([])
  }

  blocks.reduce(
    (cur, row) => {
      for (let i=0; i < slots; i++) {
        slotLen = i < slots - 1 ? 4 : 3
        const slot = row.substring(0, slotLen)
        row = row.substring(slotLen)
        const match = slot.match(blockRe)
        if (match) {
          cur[i].push(match[1])
        }
      }
      return cur
    },
    stacks
  )

  console.log(`stacks: ${JSON.stringify(stacks)}`)

  moves.reduce(
    (stacks, move) => {
      [u, n, s, d] = move.match(moveRe)
      console.log(`n:${n} s:${s} d:${d}`)
      const tmp = []
      for (let m=0; m < n; m++) {
        //stacks[d-1].push(stacks[s-1].pop())  // part1
        tmp.push(stacks[s-1].pop())
      }
      while(tmp.length > 0) { stacks[d-1].push(tmp.pop()) }
      console.log(`move:${move} stacks:${JSON.stringify(stacks)}`)
      return stacks
    },
    stacks
  )

  const answer = stacks.reduce(
    (s, stack) => s.concat(stack.pop()),
    "")
  console.log(`answer: ${answer}`)
});
