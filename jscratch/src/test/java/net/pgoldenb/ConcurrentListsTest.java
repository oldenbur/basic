package net.pgoldenb;

import com.google.common.base.Stopwatch;
import org.junit.Test;

import java.time.Duration;
import java.util.*;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.function.Consumer;

import static org.junit.Assert.assertEquals;

public class ConcurrentListsTest {

    public static <T> Set<T> set(T... ts) {
        Set<T> set = new HashSet<>();
        Arrays.asList(ts).stream().forEach(set::add);
        return set;
    }

//    public static Set<String> buildTestCowaList(String prefix, int size) {
//
//    }

    @Test
    public void cowaPrint() {
        Set<String> input = set("a", "b", "c");
        Set<String> output = new HashSet<>();
        Stopwatch watch = Stopwatch.createStarted();
        ConcurrentListsProvider.cowaConsumerLoop(
                input,
                s -> { output.add(s); System.out.println(s); },
                Duration.ofMillis(100)
        );
        watch.stop();
        System.out.format("elapsed sl: %s%n", watch);
        assertEquals(output, input);
    }

    @Test
    public void slPrint() {
        Set<String> input = set("d", "e", "f");
        Set<String> output = new HashSet<>();
        Stopwatch watch = Stopwatch.createStarted();
        ConcurrentListsProvider.slConsumerLoop(
                input,
                s -> { output.add(s); System.out.println(s); },
                Duration.ofMillis(100)
        );
        watch.stop();
        System.out.format("elapsed sl: %s%n", watch);
        assertEquals(output, input);
    }
}

class ConcurrentListsProvider {

    public static <T> void cowaConsumerLoop(Collection<T> data, Consumer<T> c, Duration delay) {
        List<T> tList = new CopyOnWriteArrayList<T>(data);
        visitListItems(c, delay, tList);
    }

    public static <T> void slConsumerLoop(Collection<T> data, Consumer<T> c, Duration delay) {
        List<T> tList = new ArrayList<T>(data);
        visitListItems(c, delay, Collections.synchronizedList(tList));
    }

    private static <T> void visitListItems(Consumer<T> c, Duration delay, List<T> tList) {
        for (T t : tList) {
            c.accept(t);
            sleepOrThrow(delay);
        }
    }

    private static void sleepOrThrow(Duration delay) {
        if (delay.isZero()) {
            return;
        }

        try {
            Thread.sleep(delay.toMillis());
        } catch (InterruptedException e) {
            throw new RuntimeException(e);
        }
    }
}