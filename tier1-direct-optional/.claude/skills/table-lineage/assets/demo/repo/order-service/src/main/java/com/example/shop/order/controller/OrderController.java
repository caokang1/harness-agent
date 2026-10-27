package com.example.shop.order.controller;

import com.example.shop.common.api.OrderApi;
import com.example.shop.common.dto.OrderItemDTO;
import com.example.shop.order.mapper.OrderItemMapper;
import java.util.List;
import javax.annotation.Resource;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class OrderController implements OrderApi {

    @Resource
    private OrderItemMapper orderItemMapper;

    @Override
    public List<OrderItemDTO> listItems(Long orderId) {
        return orderItemMapper.selectByOrderId(orderId);
    }
}
