"use strict";
// npx tsc 2022d10.ts && node 2022d10.js
exports.__esModule = true;
var fs = require("fs");
var inputRe = /^(\w+)(?: (\-?\d+))?$/;
var s = function (obj) { return JSON.stringify(obj); };
var sa = function (arr) { return arr.map(function (o) { return JSON.stringify(o); }); };
var ss = function (set) { return Array.from(set.values()); };
var Op;
(function (Op) {
    Op[Op["Addx"] = 0] = "Addx";
    Op[Op["Noop"] = 1] = "Noop";
})(Op || (Op = {}));
var Cmd = /** @class */ (function () {
    function Cmd(op, val) {
        if (val === void 0) { val = 0; }
        this.op = op;
        this.val = val;
    }
    Cmd.prototype.toString = function () {
        return this.op === Op.Noop ? 'Noop' : "Addx{".concat(this.val, "}");
    };
    return Cmd;
}());
var cmdOf = function (line) {
    var _a;
    var u;
    var op;
    var n;
    _a = line.match(inputRe), u = _a[0], op = _a[1], n = _a[2];
    return op.localeCompare("noop") === 0
        ? new Cmd(Op.Noop) : new Cmd(Op.Addx, Number(n));
};
fs.readFile('2022d10_sm.data', 'utf8', function (err, data) {
    if (err)
        throw err;
    var moves = data.split('\n').filter(function (line) { return line !== ''; }).map(function (line) { return cmdOf(line); });
    console.log("moves:".concat(sa(moves.map(function (m) { return m.toString(); }))));
});
