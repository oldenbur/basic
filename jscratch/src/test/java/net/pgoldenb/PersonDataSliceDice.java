package net.pgoldenb;

import org.junit.Test;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.HashSet;
import java.util.Set;

/*
 *  * Design Patterns
 *  * Adjacency Matrix graphs
 */

public class PersonDataSliceDice {

    @Test
    public void test1() {
        Set<Person> people = new HashSet<Person>();
        people.add(new Person("Amy", "Oldenburg", Gender.FEMALE, LocalDate.of(1977, 9, 21), "2854 Falcon Pt.", "Lafayette", "CO", 80026, 9));
        people.add(new Person("Paul", "Oldenburg", Gender.MALE, LocalDate.of(1976, 10, 10), "2854 Falcon Pt.", "Lafayette", "CO", 80026, 10));
        people.add(new Person("Guinevere", "Oldenburg", Gender.FEMALE, LocalDate.of(2010, 9, 19), "2854 Falcon Pt.", "Lafayette", "CO", 80026, 11));
        people.add(new Person("Harold", "Oldenburg", Gender.MALE, LocalDate.of(2010, 9, 19), "2854 Falcon Pt.", "Lafayette", "CO", 80026, 12));
        people.add(new Person("Mark", "Oldenburg", Gender.MALE, LocalDate.of(1951, 9, 13), "2228 Viking Dr. NW", "Rochester", "MN", 55901, 3));
        people.add(new Person("Ann", "Oldenburg", Gender.FEMALE, LocalDate.of(1952, 7, 13), "2228 Viking Dr. NW", "Rochester", "MN", 55901, 4));
        people.add(new Person("Rose", "Oldenburg", Gender.FEMALE, LocalDate.of(1923, 2, 23), "1104 Hill St.", "Galena", "IL", 60136, 2));
        people.add(new Person("Leo", "Oldenburg", Gender.MALE, LocalDate.of(1922, 12, 30), "1104 Hill St.", "Galena", "IL", 60136, 1));

        people.stream()
                .filter(p -> p.gender == Gender.FEMALE)
                .forEach(p -> p.printPerson());

    }

    enum Gender { FEMALE, MALE; }

    class Person {
        String firstName;
        String lastName;
        Gender gender;
        LocalDate dob;
        String streetAddress;
        String city;
        String state;
        int zipCode;
        int employeeId;

        private Person(
                String firstName,
                String lastName,
                Gender gender,
                LocalDate dob,
                String streetAddress,
                String city,
                String state,
                int zipCode,
                int employeeId
        ) {
            this.firstName = firstName;
            this.lastName = lastName;
            this.gender = gender;
            this.dob = dob;
            this.streetAddress = streetAddress;
            this.city = city;
            this.state = state;
            this.zipCode = zipCode;
            this.employeeId = employeeId;
        }

        public String toString() {
            DateTimeFormatter formatter = DateTimeFormatter.ofPattern("YYYY-MM-dd");
            return String.format("%-12s %-12s %-6s %s %-12s %d % 3d", firstName, lastName, gender, formatter.format(dob), state, zipCode, employeeId);
        }

        public void printPerson() {
            System.out.println(toString());
        }
    }
}
