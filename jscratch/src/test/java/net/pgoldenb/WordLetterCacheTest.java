package net.pgoldenb;

import org.junit.Test;

import java.util.*;

import static junit.framework.TestCase.assertTrue;
import static org.junit.Assert.assertFalse;

public class WordLetterCacheTest {

    @Test
    public void test1() throws InterruptedException {
        WordLetterCache cache = new WordLetterCache();
        assertFalse(cache.addWord("bad"));
        assertTrue(cache.addWord("dabba"));
        assertFalse(cache.addWord("add"));
        assertTrue(cache.addWord("DAD"));
        assertFalse(cache.addWord("bade"));
        assertFalse(cache.addWord("Dade"));
        assertTrue(cache.addWord("DEAD"));
    }

}

class WordLetterCache {

    public static final int NUM_LETTERS = 26;

    private Map<BitSet, List<String>> data = new HashMap<BitSet, List<String>>();

    public boolean addWord(String word) {

        BitSet letters = encodeLetters(word);
        System.out.format("addWord(%s) - %s%n", word, letters);

        boolean present = true;
        if (!data.containsKey(letters)) {
            present = false;
            data.put(letters, new ArrayList<String>());
        }
        data.get(letters).add(word);

        return present;
    }

    private BitSet encodeLetters(String word) {
        BitSet letters = new BitSet(NUM_LETTERS);
        for (char c : word.toLowerCase().toCharArray()) {
            letters.set((int)c - 97);
        }
        return letters;
    }

    public List<String> getWordsWithLetters(String word) {
        List<String> words = data.get(word);
        if (words == null) {
            words = Collections.emptyList();
        }
        return new ArrayList< >(words);
    }
}