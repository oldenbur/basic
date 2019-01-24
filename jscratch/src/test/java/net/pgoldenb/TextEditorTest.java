package net.pgoldenb;

import org.junit.Test;

import java.util.Deque;
import java.util.LinkedList;
import java.util.List;

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

public class TextEditorTest {

    @Test
    public void test1() {
        assertEquals("P|al", new TextEditor()
                .insertCharacter('P').insertCharacter('a').insertCharacter('u').insertCharacter('l')
                .moveCursorLeft().backspace().moveCursorLeft().moveCursorLeft().moveCursorRight()
                .toString()
        );

        assertEquals("Amy|", new TextEditor()
                .insertCharacter('A').insertCharacter('m').insertCharacter('e').insertCharacter('e')
                .backspace().backspace().insertCharacter('y')
                .moveCursorLeft().moveCursorLeft().moveCursorLeft().moveCursorLeft().moveCursorLeft()
                .moveCursorRight().moveCursorRight().moveCursorRight().moveCursorRight().moveCursorRight()
                .toString()
        );

        assertEquals("Amee|", new TextEditor()
                .insertCharacter('A').insertCharacter('m').insertCharacter('e').insertCharacter('e')
                .backspace().backspace().insertCharacter('y')
                .moveCursorLeft().moveCursorLeft().moveCursorLeft().moveCursorLeft().moveCursorLeft()
                .moveCursorRight().moveCursorRight().moveCursorRight().moveCursorRight().moveCursorRight()
                .undo().undo().moveCursorLeft().moveCursorLeft().undo()
                .toString()
        );
    }

    private static class TextEditor {

        private List<Character> buf = new LinkedList<>();
        private int cursorIndex = 0;
        private Deque<Edit> edits = new LinkedList<>();

        public TextEditor() {
            buf.add('|');
        }

        public TextEditor moveCursorLeft() {
            return moveCursorLeft(true);
        }

        private TextEditor moveCursorLeft(boolean remember) {

            validateCursor();

            if (cursorIndex <= 0) return this;

            buf.remove(cursorIndex);
            cursorIndex -= 1;
            if (remember)
                edits.push(new Edit(EditType.MOVE_L, '|'));
            buf.add(cursorIndex, '|');
            return this;
        }

        public TextEditor moveCursorRight() {
            return moveCursorRight(true);
        }

        private TextEditor moveCursorRight(boolean remember) {

            validateCursor();

            if (cursorIndex >= buf.size() - 1) return this;

            buf.remove(cursorIndex);
            cursorIndex += 1;
            if (remember)
                edits.push(new Edit(EditType.MOVE_R, '|'));
            buf.add(cursorIndex, '|');
            return this;
        }

        public TextEditor insertCharacter(char c) {
            return insertCharacter(c, true);
        }

        private TextEditor insertCharacter(char c, boolean remember) {

            validateCursor();

            buf.add(cursorIndex, c);
            if (remember)
                edits.push(new Edit(EditType.INSERT, c));
            cursorIndex += 1;
            return this;
        }

        public TextEditor backspace() {
            return backspace(true);
        }

        private TextEditor backspace(boolean remember) {

                validateCursor();

            if (cursorIndex < 1) return this;

            char c = buf.remove(cursorIndex-1);
            if (remember)
                edits.push(new Edit(EditType.DELETE, c));
            cursorIndex -= 1;
            return this;
        }

        public TextEditor undo() {

            undoCursor();
            if (edits.size() <= 0) return this;

            Edit e = edits.pop();
            if (e.type == EditType.INSERT)
                backspace(false);
            else
                insertCharacter(e.c, false);

            return this;
        }

        public void undoCursor() {

            if (edits.size() <= 0) return;

            Edit e = edits.peek();
            while (e.type == EditType.MOVE_L || e.type == EditType.MOVE_R) {
                edits.pop();
                if (e.type == EditType.MOVE_L) moveCursorRight(false);
                else moveCursorLeft(false);
                e = edits.peek();
            }
        }

        private void validateCursor() {

            if (cursorIndex < 0 || cursorIndex >= buf.size())
                throw new IllegalStateException(String.format("encountered illegal cursorIndex %d in buf: %s", cursorIndex, buf));

            if (buf.get(cursorIndex) != '|')
                throw new IllegalStateException(String.format("found unexpected character (%c) at cursor position %d in buf: %s", buf.get(cursorIndex), cursorIndex, buf));
        }

        public String toString() {
            StringBuilder b = new StringBuilder();
            for (char c : buf) b.append(c);
            return b.toString();
        }

        private enum EditType { INSERT, DELETE, MOVE_L, MOVE_R }

        private static class Edit {
            public EditType type;
            public char c;

            public Edit(EditType type, char c) {
                this.type = type;
                this.c = c;
            }
        }

    }
}
