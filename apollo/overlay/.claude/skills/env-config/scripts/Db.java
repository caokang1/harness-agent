import java.io.*;
import java.nio.file.*;
import java.sql.*;
import java.time.LocalDateTime;
import java.util.*;

/**
 * Small JDBC client for the test databases.
 *
 *   db.sh <env> <database> "<sql>"                 read only (default)
 *   db.sh <env> <database> -f file.sql             statements separated by ";\n"
 *   db.sh <env> <database> --write --confirm "<sql>"   allow writes; every write is logged
 *
 * Connection comes from ~/.config/apollo-db/<env>.properties (host, user, password).
 * The link from this machine can drop larger responses, so reads retry on a fresh connection and
 * results are capped (--max-rows, default 200): aggregate in SQL instead of pulling rows back.
 */
public class Db {
    public static void main(String[] args) throws Exception {
        List<String> rest = new ArrayList<>(Arrays.asList(args));
        boolean write = rest.remove("--write"), confirm = rest.remove("--confirm");
        int maxRows = 200;
        int i = rest.indexOf("--max-rows");
        if (i >= 0) { maxRows = Integer.parseInt(rest.get(i + 1)); rest.remove(i + 1); rest.remove(i); }
        String file = null;
        i = rest.indexOf("-f");
        if (i >= 0) { file = rest.get(i + 1); rest.remove(i + 1); rest.remove(i); }
        if (rest.size() < 2 || (file == null && rest.size() < 3)) {
            System.err.println("usage: db.sh <env> <database> [--write --confirm] [--max-rows N] (\"<sql>\" | -f file.sql)");
            System.exit(64);
        }
        if (write && !confirm) {
            System.err.println("refuse: --write needs --confirm, and only after the user approved this exact change");
            System.exit(65);
        }
        String env = rest.get(0), db = rest.get(1);
        String sql = file != null ? new String(Files.readAllBytes(Paths.get(file)), "UTF-8") : rest.get(2);
        Properties p = new Properties();
        Path conf = Paths.get(System.getProperty("user.home"), ".config", "apollo-db", env + ".properties");
        try (InputStream in = Files.newInputStream(conf)) { p.load(in); }
        String url = "jdbc:mysql://" + p.getProperty("host") + "/" + db + "?useSSL=false&allowPublicKeyRetrieval=true"
                + "&connectTimeout=5000&socketTimeout=20000&useCompression=true&characterEncoding=utf8";
        for (String raw : sql.split(";\\s*\\n")) {
            String s = raw.replaceAll("(?m)^\\s*--.*$", "").trim();
            if (s.endsWith(";")) s = s.substring(0, s.length() - 1).trim();
            if (s.isEmpty()) continue;
            boolean isRead = s.matches("(?is)^(select|show|desc|describe|explain)\\b.*");
            if (!isRead && !write) {
                System.err.println("refuse (read-only mode): " + firstLine(s));
                System.exit(65);
            }
            run(url, p, s, isRead, maxRows, env, db);
        }
    }

    static void run(String url, Properties p, String sql, boolean isRead, int maxRows, String env, String db) throws Exception {
        for (int attempt = 1; ; attempt++) {
            try (Connection c = DriverManager.getConnection(url, p.getProperty("user"), p.getProperty("password"));
                 Statement st = c.createStatement()) {
                c.setReadOnly(isRead);
                st.setMaxRows(maxRows + 1);
                long t = System.currentTimeMillis();
                System.out.println(">>> " + firstLine(sql));
                if (st.execute(sql)) {
                    try (ResultSet rs = st.getResultSet()) { print(rs, maxRows); }
                } else {
                    int n = st.getUpdateCount();
                    System.out.println("ok, updateCount=" + n);
                    log(env, db, sql, n);
                }
                System.out.println("(" + (System.currentTimeMillis() - t) + "ms)");
                System.out.flush();
                return;
            } catch (SQLException e) {
                // writes are never retried: a dropped response may still have committed
                if (!isRead || attempt >= 5 || !(e instanceof SQLNonTransientConnectionException
                        || e.getClass().getSimpleName().contains("Communications"))) throw e;
                System.out.println("  retry " + attempt + " after " + e.getClass().getSimpleName());
            }
        }
    }

    static void print(ResultSet rs, int maxRows) throws SQLException {
        ResultSetMetaData m = rs.getMetaData();
        StringJoiner head = new StringJoiner("\t");
        for (int k = 1; k <= m.getColumnCount(); k++) head.add(m.getColumnLabel(k));
        System.out.println(head);
        int n = 0;
        while (rs.next()) {
            if (++n > maxRows) { System.out.println("... truncated at " + maxRows + " rows; aggregate in SQL or raise --max-rows"); break; }
            StringJoiner row = new StringJoiner("\t");
            for (int k = 1; k <= m.getColumnCount(); k++) row.add(String.valueOf(rs.getString(k)));
            System.out.println(row);
        }
    }

    /** every write against a shared environment leaves a line in ~/.cache/apollo-env/ops.log */
    static void log(String env, String db, String sql, int n) throws IOException {
        Path dir = Paths.get(System.getProperty("user.home"), ".cache", "apollo-env");
        Files.createDirectories(dir);
        String line = LocalDateTime.now() + "\tdb\t" + env + "/" + db + "\trows=" + n + "\t" + sql.replaceAll("\\s+", " ") + "\n";
        Files.write(dir.resolve("ops.log"), line.getBytes("UTF-8"), StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    }

    static String firstLine(String s) {
        String f = s.split("\n")[0];
        return f.length() > 160 ? f.substring(0, 160) + " ..." : f;
    }
}
