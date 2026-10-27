package com.example.shop.order.mapper;

import com.example.shop.common.dto.OrderItemDTO;
import java.util.List;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface OrderItemMapper {

    @Select("select order_id, sku, qty, price from order_item where order_id = #{orderId}")
    List<OrderItemDTO> selectByOrderId(@Param("orderId") Long orderId);

    @Insert({"<script>",
            "insert into order_item (order_id, sku, qty, price) values ",
            "<foreach collection='items' item='i' separator=','>(#{orderId}, #{i.sku}, #{i.qty}, #{i.price})</foreach>",
            "</script>"})
    int insertItems(@Param("orderId") Long orderId, @Param("items") List<OrderItemDTO> items);
}
