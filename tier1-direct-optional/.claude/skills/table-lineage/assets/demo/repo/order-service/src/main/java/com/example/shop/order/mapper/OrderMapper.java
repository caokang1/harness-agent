package com.example.shop.order.mapper;

import com.example.shop.order.entity.Order;
import java.util.List;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface OrderMapper {

    int insertOrder(Order order);

    List<Order> listWithItems(Long memberId);
}
