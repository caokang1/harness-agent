package com.example.shop.order.entity;

import com.example.shop.common.dto.OrderItemDTO;
import java.util.List;
import lombok.Data;

@Data
public class Order {
    private Long id;
    private String orderNo;
    private Long memberId;
    private Long storeId;
    private Long amount;
    private List<OrderItemDTO> items;
}
