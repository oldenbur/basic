package net.pgoldenb;

import static org.junit.Assert.assertEquals;
import org.junit.Test;

import java.util.Random;
import java.util.Timer;
import java.util.TimerTask;

public class TimedTaskTest {

    @Test
    public void testTimedTask() {
        new TimedTask().doTask();
    }


}

class TimedTask {

    private volatile boolean elapsed = false;

    public void doTask() {
        Timer t = new Timer();
        t.schedule(new TimerTask(){
            @Override public void run() {
                elapsed = true;
            }
        }, 30000l);

        Random random = new Random();

        for (long iter = 0; true; iter++) {

            int rand = random.nextInt();
            int val = Math.abs(rand);
            if (val < 0) {
                System.out.format("negative val: %d  rand: %d%n", val, rand);
            }

            if (elapsed) {
                System.out.format("doTask elapsed after iter %d%n", iter);
                return;
            }
        }
    }
}