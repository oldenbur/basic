package net.pgoldenb;

import com.google.common.collect.Lists;
import org.junit.Test;

import java.util.*;

import static junit.framework.TestCase.assertEquals;
import static junit.framework.TestCase.assertFalse;
import static org.junit.Assert.assertTrue;

public class JScratchTest {

    @Test
    public void test1() {
//        assertEquals(
//                Lists.newArrayList(0, 1),
//                grayCode(1)
//        );
//        assertEquals(
//                Lists.newArrayList(0, 1, 3, 2),
//                grayCode(2)
//        );
        assertEquals(
                Lists.newArrayList(0, 1, 3, 2, 4, 5, 7, 6),
                grayCode(3)
        );
        assertEquals(
                Lists.newArrayList(0, 1, 3, 2, 4, 5, 7, 6, 12, 13, 15, 14, 8, 9, 11, 10),
                grayCode(4)
        );
    }

    public List<Integer> grayCode(int n) {
        List<Integer> codes = new ArrayList<>();
        if (n <= 0)
            return codes;
        grayRecurse(n, 0, 0, codes);
        return codes;
    }

    private void grayRecurse(int n, int r, int base, List<Integer> codes) {

        if (r >= n)
            return;

        codes.add(base);
        codes.add(base | (1 << r));
        if (r < n - 1) {
            codes.add(base | (3 << r));
            codes.add(base | (2 << r));
        }

        r += 2;
        grayRecurse(n - 2, 0, base | (1 << r), codes);
        if (r < n - 1) {
            grayRecurse(n - 2, 0, base | (3 << r), codes);
            grayRecurse(n - 2, 0, base | (2 << r), codes);
        }
    }

}
