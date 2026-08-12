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

class State {
  val = 1;
  cyc = 0;
  signals : Array<number> = [];
  buf : string = "";

  upCyc() : State {
    let add : string = (Math.abs(this.val - (this.cyc % 40)) <= 1) ? "#" : ".";
    this.buf = this.buf.concat(add);
    if ((this.cyc+1) % 40 === 0) {
      console.log(this.buf);
      this.buf = "";
    }

    this.cyc += 1;
    if (this.isCollectCyc()) {
      //console.log(`signal - cyc:${this.cyc} val:${this.val}`);
      this.signals.push(this.cyc * this.val);
    }
    //console.log(`cyc:${this.cyc} val:${this.val} add:${add}`);
    return this;
  }

  doCmd(cmd : Cmd) : State {
    if (cmd.op === Op.Addx) {
      //console.log(`Addx val:${cmd.val}`);
      this.upCyc().upCyc();
      this.val += cmd.val;
    } else {
      //console.log(`Noop`);
      this.upCyc();
    }
    return this;
  }

  isCollectCyc() : boolean {
    return (this.cyc - 20) % 40 === 0;
  }
}

function assertEquals<Type>(v1: Type, v2: Type) {
  if (v1 !== v2) {
    console.log(`FAILURE: v1:${v1} NOT EQUAL to v2:${v2}`);
  } else {
    console.log(`v1:${v1} equals v2:${v2}`);
  }
}

const testState = () => {
  let s : State = new State().doCmd(new Cmd(Op.Noop));
  assertEquals(s.val, 1);
  assertEquals(s.cyc, 1);
  s = s.doCmd(new Cmd(Op.Addx, 3));
  assertEquals(s.val, 4);
  assertEquals(s.cyc, 3);
  s = s.doCmd(new Cmd(Op.Addx, -5));
  assertEquals(s.val, -1);
  assertEquals(s.cyc, 5);
}

const cmdOf = (line: string) : Cmd => {
  let u: string
  let op: string
  let n: string
  [u, op, n] = line.match(inputRe)
  return op.localeCompare("noop") === 0 
    ? new Cmd(Op.Noop) : new Cmd(Op.Addx, Number(n));
}

fs.readFile('2022d10.data', 'utf8', (err, data) => {
  if (err) throw err;

  const s : State = 
    data.split('\n').filter(line => line !== '')
    .map(line => cmdOf(line))
    .reduce((s: State, c: Cmd) => s.doCmd(c),
    new State()); 
  const sum : number = s.signals.reduce((s: number, ss: number) => s + ss, 0);
  console.log(`signals:${sa(s.signals)} -> sum:${sum}`);
});


