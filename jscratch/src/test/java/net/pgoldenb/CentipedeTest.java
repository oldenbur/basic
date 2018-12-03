package net.pgoldenb;

import static org.junit.Assert.*;
import org.junit.Test;

import java.util.*;
import java.util.function.Consumer;

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

    @Test
    public void boardLocRequiresEquals() {
        Set<boardLoc> m = new HashSet<>();
        m.add(new boardLoc(1, 2));
        assertTrue(m.contains(new boardLoc(1, 2)));
    }

}

/**
 * Requirements:
 *   * does board cell contain segment?
 *   * where is the head and tail?
 *   * move: new head segment in unoccupied direction, tail segment disappears and becomes previous second-to-last
 *   * grow: new head segment in unoccupied direction
 */


class boardLoc {
    int x, y;

    public boardLoc(int x, int y) {
        this.x = x;
        this.y = y;
    }

    public boolean isAdjacent(boardLoc otherLoc) {
        int xDelta = Math.abs(x - otherLoc.x);
        int yDelta = Math.abs(y - otherLoc.y);
        return (xDelta == 1 && yDelta == 0) || (xDelta == 0 && yDelta == 1);
    }

    public String toString() {
        return String.format("(%d, %d)", x, y);
    }

    @Override public boolean equals(Object o) {
        return (o != null && o instanceof boardLoc && ((boardLoc)o).x == x && ((boardLoc)o).y == y);
    }

    @Override public int hashCode() {
        int result = 17;
        result = 31 * result + x;
        result = 31 * result + y;
        return result;
    }
}

class creature {

    private List<boardLoc> segList;
    private Set<boardLoc> segSet;

    public creature(List<boardLoc> locs, int boardDim) {
        segList = new LinkedList<>();
        segSet = new HashSet<>(locs.size());

        for (boardLoc loc : locs) {
            validateCreatureSegmentAdjacency(loc);
            validateCreatureSegmentConflict(loc);
            validateCreatureSegmentOnBoard(loc, boardDim);

            segList.add(loc);
            segSet.add(loc);
        }
    }

    private void validateCreatureSegmentOnBoard(boardLoc loc, int boardDim) {
        if (loc.x < 0 || loc.x >= boardDim || loc.y < 0 || loc.y >= boardDim) {
            throw new IllegalArgumentException(String.format("segment %s not on board of dimension %d", loc, boardDim));
        }
    }

    private void validateCreatureSegmentConflict(boardLoc loc) {
        if (segSet.contains(loc)) {
            throw new IllegalArgumentException(String.format("initial segment conflict: %s", loc));
        }
    }

    private void validateCreatureSegmentAdjacency(boardLoc loc) {

        boardLoc prevLoc = null;
        if (segList.size() > 0) {
            prevLoc = segList.get(segList.size()-1);
        }

        if (prevLoc != null && !loc.isAdjacent(prevLoc)) {
            throw new IllegalArgumentException(
                    String.format("initial location segments not adjacent: %s vs %s", prevLoc, loc)
            );
        }
    }

    public boolean containsLocation(boardLoc loc) {
        return segSet.contains(loc);
    }

    public int length() {
        return segList.size();
    }

    // TODO
    public creature moveTo(boardLoc loc) {
        return null;
    }
}

class Centipede {

//    enum CentipedeBoardVal { EMPTY, CREATURE }
    private int boardDim;
    private creature curCreature;

    public Centipede(int boardDim, int centLen, List<boardLoc> initCreature) {
        validateBoardDimAndCentLen(boardDim, centLen);

        this.boardDim = boardDim;
        this.curCreature = new creature(initCreature, boardDim);
    }

    public Centipede(int boardDim, int centLen) {
        this(boardDim, centLen, defaultInitCreature(boardDim, centLen));
    }

    private static void validateBoardDimAndCentLen(int boardDim, int centLen) {
        if (boardDim < 3) {
            throw new IllegalArgumentException("boardDim must be greater than 3");
        }
        if (centLen < 1 || centLen > (boardDim / 2)) {
            throw new IllegalArgumentException(String.format("centLen must be 1 <= centLen <= %d", (boardDim / 2)));
        }
    }

    private static List<boardLoc> defaultInitCreature(int boardDim, int centLen) {

        int ordX = (boardDim/2);
        int ordY = (boardDim/2);

        List<boardLoc> cLoc = new ArrayList<>(centLen);
        for (int l=0; l < centLen; l++) {
            cLoc.add(new boardLoc(ordX - l, ordY));
        }

        return cLoc;
    }

    public String toString() {
        StringBuffer b = new StringBuffer();
        b.append("+" + repeat("-", boardDim) + "+\n");
        visitBoardCells(
                boardDim,
                i -> b.append("|"),
                l -> {
                    if (curCreature.containsLocation(l)) {
                        String xStr = String.format("%d", l.x);
                        b.append(xStr.substring(xStr.length()-1));
                    } else {
                        b.append(" ");
                    }
                },
                i -> b.append("|\n")
        );
        b.append("+" + repeat("-", boardDim) + "+\n");

        return b.toString();
    }

    private static void visitBoardCells(
            int boardDim,
            Consumer<Integer> rowBeginConsumer,
            Consumer<boardLoc> cellConsumer,
            Consumer<Integer> rowEndConsumer
    ) {
        for (int y=0; y < boardDim; y++) {
            rowBeginConsumer.accept(y);
            for (int x=0; x < boardDim; x++) {
                cellConsumer.accept(new boardLoc(x, y));
            }
            rowEndConsumer.accept(y);
        }
    }

    public int length() {
        return curCreature.length();
    }

    public static String repeat(String s, int n) {
        return new String(new char[n]).replace("\0", s);
    }
}
