package net.pgoldenb;

import org.junit.Test;

import java.util.*;

import static org.junit.Assert.assertEquals;

public class JScratchTest {

    @Test
    public void test1() {
        assertEquals("ttr", removeChars("teeter", "aeiou"));
        assertEquals("abcegecba", removeChars("abcdefgfedcba", "df"));
        assertEquals("Bttl f th Vwls: Hw vs. Grzny",
                removeChars("Battle of the Vowels: Hawaii vs. Grozny", "aeiou"));
    }

    @Test(expected = ArithmeticException.class)
    public void testThrows() throws InterruptedException {
        int i = 10 / 0;
        System.out.printf("%d%n", i);
    }

    private String removeChars(String str, String remove) {

        Set<Integer> removeSet = new HashSet<>();
        for (int i=0; i < remove.length();) {
            int cp = remove.codePointAt(i);
            i += Character.charCount(cp);
            removeSet.add(cp);
        }

        StringBuilder buf = new StringBuilder();
        for (int i=0; i < str.length();) {
            int cp = str.codePointAt(i);
            i += Character.charCount(cp);
            if (!removeSet.contains(cp)) {
                buf.append(Character.toChars(cp));
            }
        }
        return buf.toString();
    }
}
