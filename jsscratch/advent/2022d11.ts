// npx tsc 2022d10.ts && node 2022d10.js

import * as fs from 'fs';

const monkeyRe =   /^Monkey (\d+):$/;
const startingRe = /^  Starting items: (.+)$/;
const opRe =       /^  Operation: new = old (. \S+)$/;
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
  insp = 0;

  constructor(items: Array<number>, op: string, testDiv: number, t: number, f: number) {
    this.items = items;
    this.op = op;
    this.testDiv = testDiv;
    this.t = t;
    this.f = f;
  }

  applyOp(old: number): number {
    const comp: Array<string> = this.op.match(/(.) (\S+)/);
    const val: number =
      comp[2].localeCompare("old") === 0 ? old : Number(comp[2]);
    return comp[1].localeCompare("+") === 0 ? old + val : old * val;
  }

  applyTest(wor: number): number {
    return (Number(wor % this.testDiv) === 0) ? this.t : this.f;
  }

  toString() : string {
    return `Monkey{items:${s(this.items)} op:${this.op} testDiv:${this.testDiv} t:${this.t} f:${this.f}`; 
  }
}

function parseMonkey(block: Array<string>): Monkey {
  return new Monkey(
    block[1].match(startingRe)[1].split(", ").map(s => Number(s)),
    block[2].match(opRe)[1],
    Number(block[3].match(testRe)[1]),
    Number(block[4].match(trueRe)[1]),
    Number(block[5].match(falseRe)[1]));
}

function doRound(monkeys: Monkey[], worryMod: number): Monkey[] {
  for (let i=0; i < monkeys.length; i++) {
    while (monkeys[i].items.length > 0) {
      monkeys[i].insp += 1;
      const it: number = monkeys[i].items.shift();
      const itOp: number = monkeys[i].applyOp(it);
      //const itBor: number = Math.trunc(itOp / 3);
      const itBor: number = itOp % worryMod;
      
      const mNext: number = monkeys[i].applyTest(itBor);
      //console.log(`i:${i} it:${it} itOp:${itOp} itBor:${itBor} mNext:${mNext}`);
      monkeys[mNext].items.push(itBor);
    }
  }
  //let i=0;
  //monkeys.forEach(m => console.log(`Monkey ${i++}: ${s(m.items)}`));
  return monkeys;
}

fs.readFile('2022d11.data', 'utf8', (err, data) => {
  if (err) throw err;

  let monkeys: Array<Monkey> =
    data.split('\n').filter(line => line !== '')
      .reduce((blocks, line) => {
        if (blocks.length < 1 || blocks[blocks.length-1].length === 6) {
          blocks.push([]);
        }
        blocks[blocks.length-1].push(line);
        return blocks;
      }, [])
      .map(block => parseMonkey(block));
  const worryMod: number = monkeys.reduce((w, m) => w * m.testDiv, 1);
  for (let i=0; i < 10000; i++) {
    monkeys = doRound(monkeys, worryMod);
  }
  let n=0;
  monkeys.forEach(m => console.log(`Monkey ${n++}: ${s(m.insp)}`));
  let insps: number[] = monkeys.map(m => m.insp);
  insps.sort((a, b) => b - a);
  console.log(`business: ${s(insps)} ${insps[0]} ${insps[1]} -> ${insps[0]*insps[1]}`);
});


