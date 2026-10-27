package com.example.shop.common.dto;

import lombok.Data;

@Data
public class DailySalesDTO {
    private String day;
    private Long storeId;
    private Integer orderCount;
    private Long amount;
}
