// https://adventofcode.com/2022/day/3
//

var fs = require('fs');

const hasWhollyContainedRange = n => {
  const result =
    (n[0] <= n[2] && n[1] >= n[3]) || (n[0] >= n[2] && n[1] <= n[3])
      ? 1 : 0
  // console.log(`n: ${n}  result: ${result}`)
  return result
}

const hasOverlappingRange = n => {
  const result = (n[1] < n[2] || n[0] > n[3]) ? 0 : 1
  console.log(`n: ${n}  result: ${result}`)
  return result
}

fs.readFile('2022d4.data', 'utf8', (err, data) => {
  if (err) throw err;

  const result = data
    .split('\n')
    .filter(line => (line !== ''))
    .reduce(
      (sum, line) => 
        //sum + hasWhollyContainedRange(
        sum + hasOverlappingRange(
          line
            .replace(/[\-,]/g, ',')
            .split(',')
            .map(s => Number(s))),
      0)
  console.log(`part1: ${result}`)
});
