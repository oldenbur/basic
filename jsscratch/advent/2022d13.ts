// npx tsc 2022d10.ts && node 2022d10.js

import * as fs from 'fs';

const reInt: RegExp = /^(\d+)(.+)/;

enum PacketType { List, Int, }

class Packet {
  type: PacketType;
  parent: Packet;
  val: number;
  packets: Packet[];

  constructor(
    type: PacketType, parent: Packet, val: number=0, packets: Packet[]=[]) {
    this.type = type;
    this.parent = parent;
    this.val = val;
    this.packets = packets;
  }

  toString(): string {
    return this.type === PacketType.Int
      ? `${this.val}` 
      : `[${this.packets.map(p => p.toString()).join(",")}]`;
  }
}

const fromString = (str: string): Packet => {
  let packet: Packet = new Packet(PacketType.List, null);
  let subStr: string = str;
  while (subStr !== ']') {
    if (subStr.charAt(0) === '[') {
      const child: Packet = new Packet(PacketType.List, packet);
      //console.log(`fromString('${subStr}', packet:${packet.toString()} add list`);
      packet.packets.push(child);
      packet = child;
      subStr = subStr.substring(1);
    } else if (subStr.charAt(0) === ',') {
      subStr = subStr.substring(1);
    } else if (subStr.charAt(0) === ']') {
      packet = packet.parent;
      subStr = subStr.substring(1);
    } else {
      const mInt: string[] = subStr.match(reInt);
      //console.log(`fromString('${subStr}', packet:${packet.toString()} add int '${mInt[1]}'`);
      packet.packets.push(
        new Packet(PacketType.Int, packet, Number(mInt[1])));
      subStr = mInt[2];
    }
  }

  //console.log(`fromString() - root:${packet.toString()}`);
  return packet;
}

class Pair {
  left: Packet;
  right: Packet;

  constructor(left: Packet, right: Packet) {
    this.left = left;
    this.right = right;
  }

  toString(): string {
    return `L:${this.left.toString()} R:${this.right.toString()}`;
  }
}

fs.readFile('2022d13_sm.data', 'utf8', (err, data) => {
  if (err) throw err;
  
  const pairs: Pair[] = 
    data.split('\n').filter(line => line !== '')
      .map(line => fromString(line))
      .reduce((pairs, p) => {
        if (pairs.length === 0 || pairs[pairs.length-1].length === 2) {
          pairs.push([]);
        }
        pairs[pairs.length-1].push(p);
        return pairs;
      }, [])
      .map(pair => new Pair(pair[0], pair[1]));
  pairs.forEach(p => console.log(p.toString()));
});


