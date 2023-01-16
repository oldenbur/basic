
export class Heap<Type> {
  data: Type[];
  comp: (v1: Type, v2: Type) => number;

  constructor(comp: (v1: Type, v2: Type) => number) {
    this.data = [];
    this.comp= comp;
  }

  size(): number {
    return this.data.length;
  }

  peek(): Type {
    if (this.data.length < 1) {
      throw new Error('Heap is empty.');
    }
    return this.data[0];
  }
  
  toString(): string {
    return this.data.join(', ');
  }
  
  add(d: Type) {
    this.data.push(d);
    this.bubbleUp(this.data.length-1);
  }

  remove(): Type {
    if (this.data.length < 1) {
      throw new Error('Heap is empty.');
    }
    
    const max: Type = this.data[0];
    if (this.data.length <= 1) {
      this.data = [];
    } else {
      this.data[0] = this.data.pop();
      this.bubbleDown(0);
    }
    return max;
  }

  parent(c: number): number { return Math.trunc((c-1)/2); }
  lChild(p: number): number { return 2*p + 1; }
  rChild(p: number): number { return 2*p + 2; }

  swap(i: number, j: number) {
    const tmp: Type = this.data[j];
    this.data[j] = this.data[i];
    this.data[i] = tmp;
  }

  bubbleUp(i: number) {
    if (i <= 0 || this.comp(this.data[i], this.data[this.parent(i)]) < 0) {
      return;
    }
    this.swap(i, this.parent(i));
    //console.log(`bubbleUp(${i}): ${this.toString()}`);
    this.bubbleUp(this.parent(i));
  }
  
  isLeaf(i: number): boolean {
    return i >= Math.floor(this.data.length / 2) && i < this.data.length;
  }

  bubbleDown(i: number) {
    if (this.isLeaf(i)) {
      return;
    }

    let lg: number = i;
    if (this.data.length > this.lChild(i) &&
      this.comp(this.data[i], this.data[this.lChild(i)]) < 0) {
      lg = this.lChild(i);
    }
    if (this.data.length > this.rChild(i) &&
      this.comp(this.data[lg], this.data[this.rChild(i)]) < 0) {
      lg = this.rChild(i);
    }
    if (lg !== i) {
      this.swap(i, lg);
      //console.log(`bubbleDown(${i}): ${this.toString()}`);
      this.bubbleDown(lg);
    }
  }
} 

function assertEquals<Type>(v1: Type, v2: Type) {
  if (v1 !== v2) {
    console.log(`FAILURE: v1:${v1} NOT EQUAL to v2:${v2}`);
  } else {
    console.log(`v1:${v1} equals v2:${v2}`);
  }
}

function testHeap() {
  const h: Heap<number> = new Heap((i, j) => i - j);
  h.add(4);
  assertEquals(h.peek(), 4);
  h.add(3);
  h.add(7);
  h.add(5);
  h.add(6);
  assertEquals(h.peek(), 7);
  console.log(h.toString());
  assertEquals(h.remove(), 7);
  assertEquals(h.peek(), 6);
  console.log(h.toString());
}


