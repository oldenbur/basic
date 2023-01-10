// npx tsc 2022d10.ts && node 2022d10.js

import * as fs from 'fs';

const inputRe = /^(\w+)(?: (\-?\d+))?$/

const s = (obj) => JSON.stringify(obj)
const sa = (arr) => arr.map(o => JSON.stringify(o))
const ss = (set) => Array.from(set.values())

enum Op { Addx, Noop, }

class Cmd {
  op: Op;
  val?: number;

  constructor(op, val = 0) {
    this.op = op;
    this.val = val;
  }

  toString() : string {
    return this.op === Op.Noop ? 'Noop' : `Addx{${this.val}}`;
  }
}

const cmdOf = (line: string) : Cmd => {
  let u: string
  let op: string
  let n: string
  [u, op, n] = line.match(inputRe)
  return op.localeCompare("noop") === 0 
    ? new Cmd(Op.Noop) : new Cmd(Op.Addx, Number(n));
}

fs.readFile('2022d10_sm.data', 'utf8', (err, data) => {
  if (err) throw err;

  const moves : Cmd[] = 
    data.split('\n').filter(line => line !== '').map(line => cmdOf(line))
  //console.log(`moves:${sa(moves.map(m => m.toString()))}`)

});


