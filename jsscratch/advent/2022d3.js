// https://adventofcode.com/2022/day/3
//

var fs = require('fs');

const commonItems = (l1, l2) => {
  const s = new Set()
  Array.from(l1).forEach(c => s.add(c))
  return Array.from(l2).filter(c => s.has(c))
}

const commonItemsAll = (lists) => {
  return lists.reduce(
    (common, list) => {
      const result = list.length < 1
	? common
	: common.length < 1
	  ? list
	  : commonItems(common, list);
      //console.log(`common: ${common}  list: ${list}  result: ${result}`)
      return result
    },
    []);
}

const scoreItem = item => {
  // A: 65 (-38) a: 97 (-96)
  let p = item.charCodeAt()
  return p < 97 ? p - 38 : p - 96;
}

const processLinePart1 = line => {
  const l1 = line.substring(0, line.length/2)
  const l2 = line.substring(line.length/2)
  const item = commonItemsAll([l1, l2])[0]
  //console.log(`item: ${item}  type: ${JSON.stringify(item)}`)

  return scoreItem(item) 
}

fs.readFile('2022d3.data', 'utf8', (err, data) => {
  if (err) throw err;

  const lines = data.split('\n');
  const pp = lines.reduce(
    (sum, line) => (line === '') ? sum : sum + processLinePart1(line),
    0)
  console.log(`part1: ${pp}`)
});

fs.readFile('2022d3_2.data', 'utf8', (err, data) => {
  if (err) throw err;

  const lines = data.split('\n');
  const groups = lines.filter(l => l !== '').reduce(
    (g, line) => {
      //console.log(`before - g: ${JSON.stringify(g)}  line: ${line}`)
      if (g.length == 0 || g[g.length-1].length % 3 == 0) {
        g.push([line])
      } else {
        g[g.length - 1].push(line)
      }
      //console.log(`after - g: ${JSON.stringify(g)}`)
      return g
    },
    [])
  const pp = groups.reduce(
    (sum, group) => {
      const item = commonItemsAll(group)[0]
      const score = scoreItem(item)
      //console.log(`group: ${group}  score: ${score}  sum: ${sum}`)
      return sum + score
    },
    0)
  console.log(`part2: ${pp}`)
});

