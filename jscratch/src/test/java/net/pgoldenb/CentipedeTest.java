package net.pgoldenb;

import static org.junit.Assert.assertEquals;
import org.junit.Test;

import java.util.SortedMap;
import java.util.TreeMap;

public class CentipedeTest {

    @Test
    public void constructorValid() {
        assertEquals(3, new Centipede(10, 3).length());
    }

    @Test(expected = IllegalArgumentException.class)
    public void constructorInsufficientBoardDim() {
        new Centipede(2, 1);
    }

    @Test(expected = IllegalArgumentException.class)
    public void constructorCentLenTooLarge() {
        new Centipede(10, 6);
    }

    @Test
    public void toStringReturns() {
        Centipede c = new Centipede(10, 3);
        System.out.println(c.toString());
    }

}


class Centipede {

//    enum CentipedeBoardVal { EMPTY, CREATURE }

    class boardLoc implements Comparable<boardLoc> {
        int i, j;

        public boardLoc(int i, int j) {
            this.i = i;
            this.j = j;
        }

        @Override
        public int compareTo(boardLoc o) {
            if (i != o.i) return i - o.i;
            else return (j - o.j);
        }
    }

    private SortedMap<boardLoc, Integer> creature;
    private int boardDim;

    public Centipede(int boardDim, int centLen) {
        this.boardDim = boardDim;

        if (boardDim < 3) {
            throw new IllegalArgumentException("boardDim must be greater than 3");
        }
        if (centLen < 1 || centLen > (boardDim/2)) {
            throw new IllegalArgumentException(String.format("centLen must be 1 <= centLen <= %d", (boardDim/2)));
        }

        int ordI = (boardDim/2);
        int ordJ = (boardDim/2);
        creature = new TreeMap<>();
        for (int l=0; l < centLen; l++) {
            creature.put(new boardLoc(ordI, ordJ - l), Integer.valueOf(l));
        }
    }

    public int length() {
        return creature.size();
    }

    public String toString() {
        StringBuffer b = new StringBuffer();
        b.append("+" + repeat("-", boardDim) + "+\n");
        for (int j=0; j < boardDim; j++) {
            for (int i=0; i < boardDim; i++) {
                boardLoc loc = new boardLoc(j, i);
                if (!creature.containsKey(loc)) {
                    b.append(" ");
                } else {
                    b.append("*");
                }
            }
            b.append("\n");
        }
        b.append("+" + repeat("-", boardDim) + "+\n");

        return b.toString();
    }

    public String repeat(String s, int n) {
        return new String(new char[n]).replace("\0", s);
    }
}
