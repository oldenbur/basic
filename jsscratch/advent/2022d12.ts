// npx tsc 2022d10.ts && node 2022d10.js

import * as fs from 'fs';
import {Heap} from './heap';

const s = (obj) => JSON.stringify(obj)

class Pt {
  r: number;
  c: number;

  constructor(r: number, c: number) {
    this.r = r;
    this.c = c;
  }

  toString(): string { return `[${this.r}, ${this.c}]`; }

  gridVal(grid: number[][]): number {
    if ( this.r < 0 || this.r >= grid.length || 
      this.c < 0 || this.c >= grid[0].length) 
    {
      throw new Error(`Expected ${this.toString()} to be within grid dimensions ${grid.length} x ${grid[0].length}`);
    }
    return grid[this.r][this.c];
  }

  equals(pt: Pt): boolean { return this.r === pt.r && this.c === pt.c; }
}

const printGrid = (grid: number[][]) => {
  grid.forEach(row => console.log(row.join()));
}

const visitGrid = (grid: number[][], visitor: (Pt, number) => void) => {
  for (let r=0; r < grid.length; r++) {
    for (let c=0; c < grid[0].length; c++) {
      visitor(new Pt(r, c), grid[r][c]);
    }
  }
}

class Searcher {
  start: Pt;
  end: Pt;
  grid: number[][];
  cost: number[][];
  neighbors: Heap<Pt>;
  prev: Map<Pt,Pt>

  constructor(grid: number[][]) {
    this.grid = grid;
    this.prev = new Map<Pt,Pt>();

    visitGrid(this.grid, (pt: Pt, val: number) => {
      if (val === 83) {
        this.start = pt;
      } else if (val === 69) {
        this.end = pt;
      }
    });
    //console.log(`start:${this.start.toString()} end:${this.end.toString()}`);

    this.cost = [];
    visitGrid(grid, (pt: Pt, val: number) => {
      if (pt.c === 0) { this.cost.push([]); }
      this.cost[pt.r].push(Number.MAX_VALUE);
    });
    //console.log(`Cost:`);
    //printGrid(this.cost);

    this.neighbors = new Heap<Pt>(
      (pt1: Pt, pt2: Pt) => pt2.gridVal(this.cost) - pt1.gridVal(this.cost));
  }

  equivalentCode(pt: Pt): number {
    return pt.gridVal(this.grid) === 83? 
          97 : pt.gridVal(this.grid) === 69 ?
          123: pt.gridVal(this.grid);
  } 

  search() {
    visitGrid(this.grid, (pt: Pt, val: number) => {
      if (val === 97 || val === 83) {
        this.cost[pt.r][pt.c] = 0;
        this.neighbors.add(pt);
      }
    });
    while(this.neighbors.size() > 0) {
      const cur: Pt = this.neighbors.remove();
      if (cur.gridVal(this.grid) === 69) {
        console.log(`goal: ${cur.toString()} - cost:${cur.gridVal(this.cost)}`);
        return cur.gridVal(this.cost);
      }
      console.log(`cur: ${cur.toString()} - cost:${cur.gridVal(this.cost)}`);
      const ns: Pt[] = [
        new Pt(cur.r-1, cur.c), new Pt(cur.r+1, cur.c),
        new Pt(cur.r, cur.c-1), new Pt(cur.r, cur.c+1)];
      for (let n of ns) {
        if (n.r < 0 || n.r >= this.grid.length || 
            n.c < 0 || n.c >= this.grid[0].length) {
          continue;
        }
        const nStep: number = n.gridVal(this.grid) === 69 ? 
          123 : n.gridVal(this.grid);
        const step: number = (nStep - cur.gridVal(this.grid));
        if (step > 1 && cur.gridVal(this.grid) !== 83) {
          //console.log(`n:${n.toString()} step(${step}) > 1 - ${n.gridVal(this.grid)} vs ${cur.gridVal(this.grid)}`);
          continue;
        }
        const nCost: number =  cur.gridVal(this.cost) + 1;
        if (nCost < n.gridVal(this.cost)) {
          this.cost[n.r][n.c] = nCost;
          this.prev.set(n, cur);
          this.neighbors.add(n);
          //console.log(`updating n:${n.toString()} nCost:${nCost} neighbors:${this.neighbors.toString()}`);
        } else {
          //console.log(`not updating n:${n.toString()} nCost:${nCost}`);
        }
      }
    }
  }

  search2() {
    visitGrid(this.grid, (pt: Pt, val: number) => {
      if (val === 97 || val === 83) {
        this.cost[pt.r][pt.c] = 0;
        this.neighbors.add(pt);
      }
    });
    while(this.neighbors.size() > 0) {
      const cur: Pt = this.neighbors.remove();
      if (cur.gridVal(this.grid) === 69) {
        console.log(`goal2: ${cur.toString()} - cost:${cur.gridVal(this.cost)}`);
        return cur.gridVal(this.cost);
      }
      console.log(`cur: ${cur.toString()} - char:${cur.gridVal(this.grid)} cost:${cur.gridVal(this.cost)}`);
      const ns: Pt[] = [
        new Pt(cur.r-1, cur.c), new Pt(cur.r+1, cur.c),
        new Pt(cur.r, cur.c-1), new Pt(cur.r, cur.c+1)];
      for (let n of ns) {
        if (n.r < 0 || n.r >= this.grid.length || 
            n.c < 0 || n.c >= this.grid[0].length) {
          continue;
        }
        const nStep: number = this.equivalentCode(n);
        const cStep: number = this.equivalentCode(cur);
        const step: number = nStep - cStep;
        //console.log(`step - n:${n.toString()} step:${step} nStep:${nStep} cStep:${cStep}`);
        if (step > 1) {
          continue;
        }
        const nCost: number =  cur.gridVal(this.cost) + 1;
        if (nCost < n.gridVal(this.cost)) {
          this.cost[n.r][n.c] = nCost;
          this.prev.set(n, cur);
          this.neighbors.add(n);
          //console.log(`updating n:${n.toString()} nCost:${nCost} neighbors:${this.neighbors.toString()}`);
        } else {
          //console.log(`not updating n:${n.toString()} nCost:${nCost} cost:${n.gridVal(this.cost)}`);
        }
      }
    }
  }
}

fs.readFile('2022d12.data', 'utf8', (err, data) => {
  if (err) throw err;
  
  const grid: number[][] = 
    data.split('\n').filter(line => line !== '')
    .map(line => {
      const row: number[] = []
      for (let i=0; i < line.length; i++) {
        row.push(line.charCodeAt(i));
      }
      return row;
    })
  //printGrid(grid);      

  //new Searcher(grid).search();
  new Searcher(grid).search2();
});


