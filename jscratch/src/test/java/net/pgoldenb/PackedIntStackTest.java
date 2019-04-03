package net.pgoldenb;

import org.junit.Test;

import java.util.*;

import static org.junit.Assert.assertEquals;

/*
 *  * Design Patterns
 *  * Adjacency Matrix graphs
 *
 *  * Dijkstras Algo
 *  * A-star Algo
 *  * Travelling Salesman
 *  * Knapsack problem
 *  * n-choose
 */

public class PackedIntStackTest {

    @Test
    public void test1() {
//        System.out.println(formatInt(32));
//        System.out.println(formatInt(31));
//        System.out.println(formatInt(-32));
//        System.out.println();
//        System.out.println(formatInt(32 << 2));
//        System.out.println(formatInt(31 << 2));
//        System.out.println(formatInt(-32 << 2));
//        System.out.println();
//        System.out.println(formatInt(32 << 4));
//        System.out.println(formatInt(31 << 4));
//        System.out.println(formatInt(-32 << 4));
//        System.out.println();
//        System.out.println(PackedIntStack.printBinary(1150921420));

        PackedIntStack s = new PackedIntStack();
        s.push(24);
        s.push(6);
        s.push(96);

        assertEquals(3, s.size());
        assertEquals(96, s.pop());
        assertEquals(2, s.size());
        assertEquals(6, s.pop());
        assertEquals(1, s.size());
        assertEquals(24, s.pop());
        assertEquals(0, s.size());
    }

    private String formatInt(int val) {
        return String.format("0x%08X", val);
    }

    static class PackedIntStack {

        private List<Integer> data = new ArrayList<>();
        private Deque<Integer> widths = new ArrayDeque<>();
        private int widthSum = 0;

        public int size() {
            return widths.size();
        }

        public void push(int val) {

            if (val <= 0)
                throw new IllegalArgumentException(String.format("PackedIntStack does not except non-positive values: %d", val));

            int wcpy = val;
            int width = 0;
            while (wcpy > 0) {
                width += 1;
                wcpy = wcpy >> 1;
            }

            int slot = widthSum / 32;
            int offset = widthSum % 32;

            int bucket = 0;
            if (slot < data.size()) {
                bucket = data.get(slot);
            }

            if (offset + width <= 32) {
                int slidVal = val << offset;
                System.out.println(String.format("Adding slidVal:\n%s\nto bucket element %d:\n%s\n",
                        printBinary(slidVal), slot, printBinary(bucket)));
                int newBucket = bucket | slidVal;
                if (slot < data.size())
                    data.set(slot, newBucket);
                else
                    data.add(newBucket);
                widths.push(width);
                widthSum += width;
            }
        }

        public int pop() {

            if (widths.size() < 1)
                throw new NoSuchElementException();

            int width = widths.pop();
            int start = widthSum - width;

            int slot = start / 32;
            int offset = start % 32;

            int bucket = data.get(slot);
            int popMask = ((1 << width) - 1) << offset;
            System.out.println(String.format("Popping popMask:\n%s\noff treeOf bucket element %d:\n%s\n",
                    printBinary(popMask), slot, printBinary(bucket)));
            int val = (bucket & popMask) >> offset;

            int bucketRemain = 0;
            if (widths.size() > 0) {
                int remainMask = (1 << (offset)) - 1;
                System.out.println(String.format("Remain mask:\n%s\n", printBinary(remainMask)));
                bucketRemain = (bucket & remainMask);
                System.out.println(String.format("Remain bucket:\n%s\n", printBinary(bucketRemain)));
            }

            widthSum -= width;
            data.set(slot, bucketRemain);

            return val;
        }

        public static String printBinary(int val) {
            return leftPad(Integer.toString((val >> 24) & 0xFF, 2), '0', 8) + " " +
                    leftPad(Integer.toString((val >> 16) & 0xFF, 2), '0', 8) + " " +
                    leftPad(Integer.toString((val >> 8) & 0xFF, 2), '0', 8) + " " +
                    leftPad(Integer.toString((val) & 0xFF, 2), '0', 8) + "\n" +
                    leftPad(Integer.toString((val >> 28) & 0xF, 16), ' ', 4) +
                    leftPad(Integer.toString((val >> 24) & 0xF, 16), ' ', 4) + " " +
                    leftPad(Integer.toString((val >> 20) & 0xF, 16), ' ', 4) +
                    leftPad(Integer.toString((val >> 16) & 0xF, 16), ' ', 4) + " " +
                    leftPad(Integer.toString((val >> 12) & 0xF, 16), ' ', 4) +
                    leftPad(Integer.toString((val >> 8) & 0xF, 16), ' ', 4) + " " +
                    leftPad(Integer.toString((val >> 4) & 0xF, 16), ' ', 4) +
                    leftPad(Integer.toString((val) & 0xF, 16), ' ', 4);
        }

        public static String leftPad(String data, char c, int width) {
            StringBuilder b = new StringBuilder(data);
            while (b.length() < width)
                b.insert(0, c);
            return b.toString();
        }

    }
}
