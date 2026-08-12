var fs = require('fs');

const lPlan = (grid) => {
  const plan = []
  grid.forEach((row, r) => {
    plan.push([])
    let max = 0
    row.forEach((n, i) => {
      if (n > max) {
        max = n
      }
      plan[r].push(max)
    })
  })
  return plan
}

const rPlan = (grid) => {
  const plan = []
  for(let r=0; r < grid.length; r++) {
    plan.push([])
    let max = 0;
    for (let c=grid[0].length - 1; c >= 0; c--) {
      if (grid[r][c] > max) {
        max = grid[r][c]
      }
      plan[r].unshift(max)
    }
  }
  return plan
}

const tPlan = (grid) => {
  const plan = []
  grid.forEach((row, r) => plan.push([]))
  for (let c=0; c < grid[0].length; c++) {
    let max = 0;
    for(let r=0; r < grid.length; r++) {
      if (grid[r][c] > max) {
        max = grid[r][c]
      }
      plan[r].push(max)
    }
  }
  return plan
}

const bPlan = (grid) => {
  const plan = []
  grid.forEach((row, r) => plan.push([]))
  for (let c=0; c < grid[0].length; c++) {
    let max = 0;
    for(let r=grid.length - 1; r >= 0; r--) {
      if (grid[r][c] > max) {
        max = grid[r][c]
      }
      plan[r].push(max)
    }
  }
  return plan
}

const calcVis = (grid) => {
  const lv = lPlan(grid)
  const rv = rPlan(grid)
  const tv = tPlan(grid)
  const bv = bPlan(grid)
  let vis = 0
  grid.forEach((row, r) => {
    if (r === 0 || r === grid.length-1) {
      vis += row.length
      return
    }
    row.forEach((tree, c) => {
      if (c === 0 || c === row.length-1 
          || tree > lv[r][c-1] || tree > rv[r][c+1]
          || tree > tv[r-1][c] || tree > bv[r+1][c]) {
        vis += 1
      }
    })
  })
  return vis
}

const inBounds = (grid, coord) => 
  (coord.c >= 0 && coord.c < grid[0].length
    && coord.r >= 0 && coord.r < grid.length)

const look = (grid, coord, inc) => {
  const h = grid[coord.r][coord.c]
  let scene = 0
  coord.c += inc.c
  coord.r += inc.r
  while (inBounds(grid, coord) && grid[coord.r][coord.c] < h) {
    //console.log(`look - coord:${JSON.stringify(coord)} h:${h} vs. t:${grid[coord.r][coord.c]}`)
    scene += 1
    coord.c += inc.c
    coord.r += inc.r
  }
  if (inBounds(grid, coord)) {
    scene += 1
  }
  //console.log(`look - coord:${JSON.stringify(coord)} inc:${JSON.stringify(inc)} scene:${scene}`)
  return scene
}

const calcScene = (grid) => {
  let max = 0
  grid.forEach((row, r) => {
    row.forEach((t, c) => {
      let scene = 
        look(grid, {r, c}, {r:-1, c:0})
        * look(grid, {r, c}, {r:1, c:0})
        * look(grid, {r, c}, {r:0, c:-1})
        * look(grid, {r, c}, {r:0, c:1})
      if (scene > max) {
        max = scene
      }
    })
  })
  return max
}

fs.readFile('2022d8.data', 'utf8', (err, data) => {
  if (err) throw err;

  const grid = []

  const lines = data.split('\n').filter(line => line !== '')
    .forEach(line => {
      const row = []
      for (let c of line) { row.push(Number(c)) }
      grid.push(row)
    })
  let vis = calcVis(grid)
  console.log(`answer1:${vis}`)

  let scene = calcScene(grid)
  console.log(`answer2:${scene}`)
});

