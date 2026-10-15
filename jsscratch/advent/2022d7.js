var fs = require('fs');

const cmdRe = /^\$ ([\w]+)(?: (\S+))?/
const dirRe = /^dir (\S+)/
const fileRe = /^(\d+) (\S+)/
const upRe = /^\.\.$/
  
let loc = []
const root = new Map()

const nav = (dir) => dir.reduce((f, d) => f.get(d), root)

const printRoot = () => {
  console.log(`/`)
  print(root, '  ')
}

const print = (dir, indent) => {
  dir.forEach((v, k) => {
    if (typeof(v) === 'number')
      console.log(`${indent}${v} ${k}`)
  })
  dir.forEach((v, k) => {
    if (v instanceof Map) {
      console.log(`${indent}${k}/`)
      print(v, `${indent}  `)
    }
  })
}

const sums = (dir) => {
  sum = 0
  dir.forEach((v, k) => {
    if (v instanceof Map) sum += sums(v)
  })
  dir.forEach((v, k) => {
    if (typeof(v) === 'number' && k !== '__TOTAL') sum += v
  })
  dir.set('__TOTAL', sum)
  return sum
}

const visitDirs = (dir, visitor) => {
  dir.forEach((v, k) => {
    if (v instanceof Map) visitDirs(v, visitor)
  })
  visitor(dir)
}

const cd = (dir) => {
  if (dir === "/") {
    loc = []
  } else if (dir.match(upRe) != null) {
    loc.pop()
  } else {
    loc.push(dir)
  }
  //console.log(`cd dir:${dir} loc:${JSON.stringify(loc)}`)
}

const ls = (lines) => {
  wd = loc.length < 1 ? root : nav(loc) 
  while(lines.length > 0) {
    dir = lines[0].match(dirRe)
    if (dir != null) {
      wd.set(dir[1], new Map())
      lines.shift()
      //console.log(`ls dir ${dir[1]} wd:${[...wd.entries()]}`)
      continue
    }
    file = lines[0].match(fileRe)
    if (file != null) {
      wd.set(file[2], Number(file[1]))
      lines.shift()
      //console.log(`ls file ${file[2]} wd:${[...wd.entries()]}`)
      continue
    }
    return
  }
}

const doCmd = (cmd, lines) => {
  //console.log(`cmd:${cmd}`)
  switch(cmd[1]) {
    case "cd":
      cd(cmd[2])
      break
    case "ls":
      ls(lines)
      break
  }
}

fs.readFile('2022d7.data', 'utf8', (err, data) => {
  if (err) throw err;

  const lines = data.split('\n').filter(line => line !== '')

  while (lines.length > 0) {
    doCmd(lines.shift().match(cmdRe), lines)
  }
  sums(root)
  //printRoot()

  let remaining = 70000000 - root.get('__TOTAL')
  let magicNum = 30000000 - remaining
  let answer = Number.MAX_SAFE_INTEGER
  visitDirs(root, (dir) => {
    dirSize = dir.get('__TOTAL')
    if (dirSize >= magicNum && dirSize < answer) {
      answer = dirSize
    }
  })
  console.log(`root:${root.get('__TOTAL')} answer:${answer}`)
});

