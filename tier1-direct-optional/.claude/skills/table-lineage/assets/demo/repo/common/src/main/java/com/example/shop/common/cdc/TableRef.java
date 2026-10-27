package com.example.shop.common.cdc;

/** One subscribed table of the binlog stream. */
public class TableRef {
    private final String db;
    private final String table;

    public TableRef(String db, String table) {
        this.db = db;
        this.table = table;
    }

    public boolean is(String db, String table) {
        return this.db.equals(db) && this.table.equals(table);
    }
}
