package com.example.shop.common.dto;

import lombok.Data;

@Data
public class StockDTO {
    private Long id;
    private String sku;
    private Long storeId;
    private Integer qty;
}
