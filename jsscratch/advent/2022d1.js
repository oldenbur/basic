// https://adventofcode.com/2022/day/1
//

var fs = require('fs');

console.log('Advent 2022 Day 1')

//let top = [0];  // PART 1
let top = [0, 0, 0];

let updateTop = (s, t) => {
  let l = t.length;
  for (let i=0; i < l; i++) {
    if (s > t[i]) {
      t.splice(i, 0, s);
      return t.slice(0, l);
    }
  }
  return t;
};

let summer = (s, t) => {
  if (t.length < 1) {
    return s;
  }
  return summer(s + t[0], t.slice(1));
}

fs.readFile('2022d1.data', 'utf8', (err, data) => {
  if (err) throw err;

  let e = 0;
  const lines = data.split('\n');
  for (let line of lines) {
    if (line === '') {
      top = updateTop(e, top);
      e = 0;
    } else{
      e += Number(line);
    }
  }
  top = updateTop(e, top);
  console.log(`max: ${summer(0, top)}`);
});

