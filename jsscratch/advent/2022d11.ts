// npx tsc 2022d10.ts && node 2022d10.js

import * as fs from 'fs';

const monkeyRe =   /^Monkey (\d+):$/;
const startingRe = /^  Starting items: (.+)$/;
const opRe =       /^  Operation; new = (\s+) (.) (\s+)$/;
const testRe =     /^  Test: divisible by (\d+)$/;
const trueRe =     /^    If true: throw to monkey (\d+)$/;
const falseRe =    /^    If false: throw to monkey (\d+)$/;

const s = (obj) => JSON.stringify(obj)
const sa = (arr) => arr.map(o => JSON.stringify(o))
const ss = (set) => Array.from(set.values())

class Monkey {
  items: Array<number>;
  op: string;
  testDiv: number;
  t: number;
  f: number;

  constructor(items: Array<number>, op: string, testDiv: number, t: number, f: number) {
    this.items = items;
    this.op = op;
    this.testDiv = testDiv;
    this.t = t;
    this.f = f;
  }

  toString() : string {
    return `Monkey{items:${s(this.items)} op:${this.op} testDiv:${this.testDiv} t:${this.t} f:${this.f}`; 
  }
}

fs.readFile('2022d11_sm.data', 'utf8', (err, data) => {
  if (err) throw err;

    data.split('\n').filter(line => line !== '')
      .reduce((blocks, line) => {
        if (blocks.length < 1 || blocks[blocks.length-1].length === 6) {
          blocks.push([]);
        }
        blocks[blocks.length-1].push(line);
        return blocks;
      }, [])
      .map(block => console.log(s(block)));
});


