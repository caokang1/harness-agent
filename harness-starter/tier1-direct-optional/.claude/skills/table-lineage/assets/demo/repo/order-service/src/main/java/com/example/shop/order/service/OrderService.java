package com.example.shop.order.service;

import com.example.shop.order.entity.Order;
import com.example.shop.order.entity.Refund;
import com.example.shop.order.mapper.OrderItemMapper;
import com.example.shop.order.mapper.OrderMapper;
import javax.annotation.Resource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class OrderService {

    @Resource
    private OrderMapper orderMapper;
    @Resource
    private OrderItemMapper orderItemMapper;
    @Resource
    private RefundService refundService;

    @Transactional
    public Long create(Order order) {
        orderMapper.insertOrder(order);
        orderItemMapper.insertItems(order.getId(), order.getItems());
        return order.getId();
    }

    public void refund(Order order) {
        Refund refund = new Refund();
        refund.setOrderId(order.getId());
        refund.setAmount(order.getAmount());
        refundService.save(refund);
    }
}
