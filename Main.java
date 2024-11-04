class Printer2 {
    public static void print() {
        System.out.println("Hello World!");
    }
}

class Printer {
    public static void print() {
        Printer2.print();
    }
}

public class Main {
    static int a = 1;
    public static void main(String[] args) {
        Printer.print();
    }
}
