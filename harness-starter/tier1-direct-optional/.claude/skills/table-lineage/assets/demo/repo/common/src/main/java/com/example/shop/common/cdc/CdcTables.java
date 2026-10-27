package com.example.shop.common.cdc;

import java.util.Arrays;
import java.util.LinkedList;
import java.util.List;

/** Tables each report listener subscribes to. */
public final class CdcTables {

    public static final List<TableRef> ORDER_TABLES = Arrays.asList(new TableRef("shop_order", "orders"));

    public static final List<TableRef> REFUND_TABLES = Arrays.asList(new TableRef("shop_order", "refund"));

    public static final List<TableRef> STORE_TABLES = new LinkedList<TableRef>() {{
        add(new TableRef("shop_member", "store"));
    }};

    private CdcTables() {
    }
}
