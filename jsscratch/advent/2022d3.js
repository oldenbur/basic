// https://adventofcode.com/2022/day/3
//

var fs = require('fs');

const processLine = line => {
  l1 = line.substring(0, line.length/2)
  l2 = line.substring(line.length/2)

  const s = new Set()
  Array.from(l1).forEach(c => s.add(c))
  item = Array.from(l2).filter(c => s.has(c))[0]

  let p = item.charCodeAt()
  let pp = p < 97 ? p - 38 : p - 96;
  //console.log(`l1: ${l1}  l2: ${l2}  item: ${item}  pp: ${pp}`)
  return pp
}

// A: 65 (-38) a: 97 (-96)

fs.readFile('2022d3.data', 'utf8', (err, data) => {
  if (err) throw err;

  let pp = 0;
  const lines = data.split('\n');
  for (let line of lines) {
    if (line === '') {
      continue
    }

    pp += processLine(line)

  }
  console.log(`priority: ${pp}`)
});

