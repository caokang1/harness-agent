package com.example.shop.report.mapper;

import com.example.shop.common.dto.DailySalesDTO;
import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface DailySalesMapper {

    int upsert(@Param("day") String day, @Param("amount") long amount);

    @Select("select day, store_id, order_count, amount from daily_sales where day = #{day}")
    List<DailySalesDTO> listByDay(@Param("day") String day);

    @Select("select d.day, d.amount, s.store_name from daily_sales d left join store s on d.store_id = s.id where d.day like concat(#{month}, '%')")
    List<DailySalesDTO> listByMonth(@Param("month") String month);
}
