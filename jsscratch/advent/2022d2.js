// https://adventofcode.com/2022/day/1
//

var fs = require('fs');

const part1 = (t, y) => {
  switch(t){
    case 'A':
      switch(y){
        case 'X': return 4
        case 'Y': return 8
        case 'Z': return 3
      }; break;
    case 'B':
      switch(y){
        case 'X': return 1
        case 'Y': return 5
        case 'Z': return 9
      }; break;
    case 'C':
      switch(y){
        case 'X': return 7
        case 'Y': return 2
        case 'Z': return 6
      }; break;
  }
}

const part2 = (t, y) => {
  switch(t){
    case 'A':
      switch(y){
        case 'X': return part1(t, 'Z') 
        case 'Y': return part1(t, 'X')
        case 'Z': return part1(t, 'Y') 
      }; break;
    case 'B':
      switch(y){
        case 'X': return part1(t, 'X')
        case 'Y': return part1(t, 'Y')
        case 'Z': return part1(t, 'Z')
      }; break;
    case 'C':
      switch(y){
        case 'X': return part1(t, 'Y')
        case 'Y': return part1(t, 'Z')
        case 'Z': return part1(t, 'X')
      }; break;
  }
}

fs.readFile('2022d2.data', 'utf8', (err, data) => {
  if (err) throw err;

  let e = 0;
  const lines = data.split('\n');
  let cumScore = 0;
  for (let line of lines) {
    if (line === '') {
      continue
    }
    [t, y] = line.split(' ');

    //console.log(`them: ${t}  you: ${y} - score: ${score}`)
    cumScore += part2(t, y) 
  }
  console.log(`cumScore: ${cumScore}`)
});

