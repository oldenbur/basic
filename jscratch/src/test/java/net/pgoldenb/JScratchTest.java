package net.pgoldenb;

import static java.util.stream.Collectors.toList;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.google.common.collect.Lists;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;
import org.junit.Test;

public class JScratchTest {

  /**
   * Roomba - given a grid with dimensions w x h, determine the number of possible paths a robot in
   * the upper left hand corner can take to reach the bottom right corner by only moving right or
   * down.
   */
  @Test
  public void testPaths() {
    assertEquals(2, numPaths(2, 2));
    assertEquals(3, numPaths(3, 2));
    assertEquals(3, numPaths(2, 3));
    assertEquals(6, numPaths(3, 3));
    assertEquals(10, numPaths(4, 3));
  }

  int numPaths(int w, int h) {
    return numPathsR(w, h, 1);
  }

  int numPathsR(int w, int h, int sum) {
    if (w <= 1 || h <= 1) {
      return sum;
    }

    return numPathsR(w - 1, h, sum) + numPathsR(w, h - 1, sum);
  }

  /**
   * 1D chess - given a board with pawns, determine if the outcome is possible given the starting
   * setup.
   */
  @Test
  public void testBoards() {
    assertTrue(isValidOutcome("L_L__R_R", "__LLRR__"));
    assertTrue(isValidOutcome("L_L__R_R", "___LLR_R"));
    assertTrue(isValidOutcome("L_L__R_R", "L_LRR___"));
    assertFalse(isValidOutcome("L_L__R_R", "LL___R_R"));
    assertFalse(isValidOutcome("L_L__R_R", "____LLRR"));
    assertFalse(isValidOutcome("L_L__R_R", "L__RL__R"));
    assertFalse(isValidOutcome("L_L__R_R", "__LLRR_"));
  }

  private class BoardConfig {

    List<Integer> lPos = new ArrayList<>();
    List<Integer> rPos = new ArrayList<>();
  }

  BoardConfig analyzeBoard(String start) {
    BoardConfig c = new BoardConfig();
    for (int i = 0; i < start.length(); i++) {
      char cur = start.charAt(i);
      if (cur == 'L') {
        c.lPos.add(i);
        if (!c.rPos.isEmpty()) {
          throw new IllegalStateException("Unexpected L to the right of R at position " + i);
        }
      }
      if (cur == 'R') {
        c.rPos.add(i);
      }
    }
    return c;
  }

  boolean isValidOutcome(String start, String end) {
    try {
      if (start.length() != end.length()) {
        return false;
      }
      BoardConfig startConfig = analyzeBoard(start);
      BoardConfig endConfig = analyzeBoard(end);

      if (startConfig.lPos.size() != endConfig.lPos.size()
          || startConfig.rPos.size() != endConfig.rPos.size()) {
        return false;
      }

      for (int l = 0; l < startConfig.lPos.size(); l++) {
        if (startConfig.lPos.get(l) > endConfig.lPos.get(l)) {
          return false;
        }
      }
      for (int r = 0; r < startConfig.rPos.size(); r++) {
        if (startConfig.rPos.get(r) < endConfig.rPos.get(r)) {
          return false;
        }
      }
    } catch (Exception e) {
      return false;
    }

    return true;
  }
}
