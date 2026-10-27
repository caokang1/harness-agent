package com.example.shop.order.controller;

import com.example.shop.order.entity.Order;
import com.example.shop.order.service.OrderService;
import javax.annotation.Resource;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/order")
public class OrderCreateController {

    @Resource
    private OrderService orderService;

    @PostMapping("/create")
    public Long create(@RequestBody Order order) {
        return orderService.create(order);
    }

    @PostMapping("/refund")
    public void refund(@RequestBody Order order) {
        orderService.refund(order);
    }
}
