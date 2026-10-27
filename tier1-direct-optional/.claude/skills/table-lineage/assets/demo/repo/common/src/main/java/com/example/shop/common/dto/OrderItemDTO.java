package com.example.shop.common.dto;

import lombok.Data;

@Data
public class OrderItemDTO {
    private Long orderId;
    private String sku;
    private Integer qty;
    private Long price;
}
