public abstract class Main {
    public static void main(String[] args) {
        float f = 32.20000076293945f;
        System.out.println(multby2(f));
        //String s = "Hello";
        //System.out.println(s + " World!");
    }

    public static int multby2(int x) {
        return x * 2;
    }

    public static float multby2(float x) {
        return x * 2;
    }
}
