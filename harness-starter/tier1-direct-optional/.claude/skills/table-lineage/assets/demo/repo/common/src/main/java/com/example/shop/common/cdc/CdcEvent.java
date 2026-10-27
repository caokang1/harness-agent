package com.example.shop.common.cdc;

import java.util.List;
import lombok.Data;

/** A row change read from the binlog. */
@Data
public class CdcEvent {
    private String db;
    private String table;
    private String day;
    private Long id;
    private String json;

    public boolean matches(List<TableRef> refs) {
        return refs.stream().anyMatch(r -> r.is(db, table));
    }
}
