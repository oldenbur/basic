"use strict";
exports.__esModule = true;
exports.Heap = void 0;
var Heap = /** @class */ (function () {
    function Heap(comp) {
        this.data = [];
        this.comp = comp;
    }
    Heap.prototype.size = function () {
        return this.data.length;
    };
    Heap.prototype.peek = function () {
        if (this.data.length < 1) {
            throw new Error('Heap is empty.');
        }
        return this.data[0];
    };
    Heap.prototype.toString = function () {
        return this.data.join(', ');
    };
    Heap.prototype.add = function (d) {
        this.data.push(d);
        this.bubbleUp(this.data.length - 1);
    };
    Heap.prototype.remove = function () {
        if (this.data.length < 1) {
            throw new Error('Heap is empty.');
        }
        var max = this.data[0];
        if (this.data.length <= 1) {
            this.data = [];
        }
        else {
            this.data[0] = this.data.pop();
            this.bubbleDown(0);
        }
        return max;
    };
    Heap.prototype.parent = function (c) { return Math.trunc((c - 1) / 2); };
    Heap.prototype.lChild = function (p) { return 2 * p + 1; };
    Heap.prototype.rChild = function (p) { return 2 * p + 2; };
    Heap.prototype.swap = function (i, j) {
        var tmp = this.data[j];
        this.data[j] = this.data[i];
        this.data[i] = tmp;
    };
    Heap.prototype.bubbleUp = function (i) {
        if (i <= 0 || this.comp(this.data[i], this.data[this.parent(i)]) < 0) {
            return;
        }
        this.swap(i, this.parent(i));
        //console.log(`bubbleUp(${i}): ${this.toString()}`);
        this.bubbleUp(this.parent(i));
    };
    Heap.prototype.isLeaf = function (i) {
        return i >= Math.floor(this.data.length / 2) && i < this.data.length;
    };
    Heap.prototype.bubbleDown = function (i) {
        if (this.isLeaf(i)) {
            return;
        }
        var lg = i;
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
    };
    return Heap;
}());
exports.Heap = Heap;
function assertEquals(v1, v2) {
    if (v1 !== v2) {
        console.log("FAILURE: v1:".concat(v1, " NOT EQUAL to v2:").concat(v2));
    }
    else {
        console.log("v1:".concat(v1, " equals v2:").concat(v2));
    }
}
function testHeap() {
    var h = new Heap(function (i, j) { return i - j; });
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
